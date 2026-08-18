"""deskill-bench runner: builds trials, calls the API, writes JSONL. Resumable.

Usage:
  python -m evals.bench.runner exp1 --dry-run
  python -m evals.bench.runner exp1 --yes [--out evals/results/exp1.jsonl]
  python -m evals.bench.runner exp2 --yes [--out evals/results/exp2.jsonl]
"""
import argparse
import json
import random
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .conditions import (
    BASE_SYSTEM, installed_system, loaded_continuation, parse_load,
    referenced_messages, trigger_user_message,
)
from .domains import CHECKABLE, TARGETS, all_domains, distractors
from .skills_gen import build_project, nested_sets, render_block

MODEL = 'claude-opus-5'
PRICE_IN, PRICE_OUT = 5.00, 25.00  # $/MTok, Claude Opus 5


@dataclass(frozen=True)
class Trial:
    trial_id: str
    exp: str
    target: str
    paraphrase_idx: int
    task: str
    n: int = 0
    condition: str = ''
    order_seed: int = 0


def exp1_trials(seed: int = 7) -> list[Trial]:
    rng = random.Random(seed)
    trials = []
    for n in (10, 25, 50, 100):
        for d in TARGETS:
            for i, task in enumerate(d.task_paraphrases[:3]):
                trials.append(Trial(
                    trial_id=f'exp1-n{n}-{d.name}-p{i}', exp='exp1', target=d.name,
                    paraphrase_idx=i, task=task, n=n, order_seed=rng.randrange(1 << 30)))
    return trials


def exp2_trials(seed: int = 7) -> list[Trial]:
    rng = random.Random(seed)
    trials = []
    for d in CHECKABLE:
        for i, task in enumerate(d.task_paraphrases[:3]):
            for condition in ('installed', 'referenced'):
                trials.append(Trial(
                    trial_id=f'exp2-{condition}-{d.name}-p{i}', exp='exp2', target=d.name,
                    paraphrase_idx=i, task=task, n=25 if condition == 'installed' else 0,
                    condition=condition, order_seed=rng.randrange(1 << 30)))
    return trials


def _text_of(response) -> str:
    return ''.join(b.text for b in response.content if b.type == 'text')


def _call(client, system: str, messages: list[dict], max_tokens: int):
    # No refusal fallbacks on purpose: a silent model switch would corrupt the
    # measurement. Refusals are recorded as error rows instead.
    return client.messages.create(
        model=MODEL, max_tokens=max_tokens, system=system, messages=messages)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def run(exp: str, out: Path, dry_run: bool, yes: bool, seed: int) -> int:
    trials = exp1_trials(seed) if exp == 'exp1' else exp2_trials(seed)
    done = set()
    if out.exists():
        done = {json.loads(line)['trial_id'] for line in out.read_text(encoding='utf-8').splitlines() if line}
    todo = [t for t in trials if t.trial_id not in done]
    print(f'{exp}: {len(trials)} trials, {len(done)} done, {len(todo)} to run')

    tmp = Path(tempfile.mkdtemp(prefix='deskill-bench-'))
    build_project(tmp, all_domains())
    sets = nested_sets(seed)
    by_name = {d.name: d for d in all_domains()}

    def block_for(trial: Trial) -> str:
        if trial.exp == 'exp1':
            names = [d.name for d in sets[trial.n]]
        else:  # installed: the checkable target among 24 distractors
            names = [trial.target] + [d.name for d in distractors()[:24]]
        random.Random(trial.order_seed).shuffle(names)
        return render_block(tmp, names)

    # cost gate
    est_in = est_out = 0
    for t in todo:
        est_in += _estimate_tokens(block_for(t)) + 300
        est_out += 400
        if t.condition == 'installed':
            est_in += _estimate_tokens(block_for(t)) + 400  # possible stage 2
    cost = est_in / 1e6 * PRICE_IN + est_out / 1e6 * PRICE_OUT
    print(f'estimated worst-case: ~{est_in:,} in / ~{est_out:,} out tokens ≈ ${cost:.2f} ({MODEL})')
    if dry_run:
        if todo:
            t = todo[0]
            print('\n--- sample trial ---')
            print(f'id: {t.trial_id}')
            print(f'system (truncated):\n{installed_system(block_for(t))[:1200]}...')
            print(f'user: {t.task}')
        return 0
    if not yes:
        print('pass --yes to spend, or --dry-run to preview')
        return 1

    import anthropic
    client = anthropic.Anthropic()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('a', encoding='utf-8') as f:
        for i, t in enumerate(todo, 1):
            row = {'trial_id': t.trial_id, 'exp': t.exp, 'target': t.target,
                   'paraphrase_idx': t.paraphrase_idx, 'n': t.n, 'condition': t.condition}
            try:
                if t.exp == 'exp1' or t.condition == 'installed':
                    system = installed_system(block_for(t))
                    messages = [{'role': 'user', 'content': trigger_user_message(t.task)}]
                    r1 = _call(client, system, messages, 512 if t.exp == 'exp1' else 1024)
                    reply = _text_of(r1)
                    predicted = parse_load(reply)
                    row.update(predicted=predicted, triggered=predicted == t.target,
                               stop_reason=r1.stop_reason)
                    if t.exp == 'exp2':
                        if predicted == t.target:
                            messages += loaded_continuation(reply.strip(), by_name[t.target].body)
                            r2 = _call(client, system, messages, 1024)
                            reply = _text_of(r2)
                        row.update(reply=reply, success=by_name[t.target].checker(reply))
                else:  # referenced
                    r = _call(client, BASE_SYSTEM,
                              referenced_messages(by_name[t.target].body, t.task), 1024)
                    reply = _text_of(r)
                    row.update(reply=reply, stop_reason=r.stop_reason,
                               success=by_name[t.target].checker(reply))
            except Exception as e:  # record and continue — reruns resume past done rows
                row.update(error=f'{type(e).__name__}: {e}')
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(f'[{i}/{len(todo)}] {t.trial_id}: '
                  f'{row.get("error") or row.get("success", row.get("triggered"))}')
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='deskill-bench')
    p.add_argument('exp', choices=['exp1', 'exp2'])
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--seed', type=int, default=7)
    a = p.parse_args(argv)
    out = a.out or Path('evals/results') / f'{a.exp}.jsonl'
    return run(a.exp, out, a.dry_run, a.yes, a.seed)


if __name__ == '__main__':
    sys.exit(main())
