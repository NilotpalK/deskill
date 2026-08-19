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
    BASE_SYSTEM, installed_system, loaded_continuation, padded_system, parse_load,
    referenced_messages, trigger_user_message,
)
from .domains import CHECKABLE, TARGETS, all_domains, distractors
from .padding import transcript
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
    pad_k: int = 0        # exp3: thousands of transcript tokens between block and task


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


def exp3_trials(seed: int = 7) -> list[Trial]:
    """Context padding at fixed N=100. ONE block order and one transcript per pad
    level — the whole system prompt is then identical across a level's trials, so
    prompt caching pays for all but the first call."""
    rng = random.Random(seed)
    trials = []
    for pad_k in (25, 50, 100):
        order_seed = rng.randrange(1 << 30)
        for d in TARGETS:
            for i, task in enumerate(d.task_paraphrases[:3]):
                trials.append(Trial(
                    trial_id=f'exp3-pad{pad_k}k-{d.name}-p{i}', exp='exp3', target=d.name,
                    paraphrase_idx=i, task=task, n=100, order_seed=order_seed, pad_k=pad_k))
    return trials


def _text_of(response) -> str:
    return ''.join(b.text for b in response.content if b.type == 'text')


def _call_api(client, system: str, messages: list[dict], max_tokens: int,
              model: str) -> tuple[str, str]:
    # No refusal fallbacks on purpose: a silent model switch would corrupt the
    # measurement. Refusals are recorded as error rows instead.
    r = client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=messages)
    return _text_of(r), r.stop_reason


def _resolve_openrouter_key() -> str:
    import os
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        env = Path('.env')
        if env.is_file():
            for line in env.read_text(encoding='utf-8').splitlines():
                name, _, val = line.partition('=')
                if name.strip().startswith('OPENROUTER') and val.strip():
                    key = val.strip().strip('"\'')
                    break
    if not key:
        raise SystemExit('no OpenRouter key: set OPENROUTER_API_KEY or put '
                         'OPENROUTER_API_KEY=... in .env (gitignored)')
    return key


def _openrouter_prices(model: str) -> tuple[float, float] | None:
    """($/MTok prompt, $/MTok completion) from the public catalog, or None."""
    import urllib.request
    try:
        with urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=15) as r:
            data = json.load(r)
        for m in data['data']:
            if m['id'] == model:
                p = m['pricing']
                return float(p['prompt']) * 1e6, float(p['completion']) * 1e6
    except Exception:
        pass
    return None


def _call_openrouter(system: str, messages: list[dict], max_tokens: int,
                     model: str, key: str) -> tuple[str, str]:
    import time

    import httpx
    payload = {
        'model': model,
        'max_tokens': max(max_tokens, 4096),  # headroom: reasoning models spend completion tokens thinking
        'messages': [{'role': 'system', 'content': system}, *messages],
    }
    last = None
    for attempt in range(4):
        last = httpx.post('https://openrouter.ai/api/v1/chat/completions',
                          headers={'Authorization': f'Bearer {key}'},
                          json=payload, timeout=600)
        if last.status_code == 429 or last.status_code >= 500:
            time.sleep(2 ** attempt * 2)
            continue
        last.raise_for_status()
        data = last.json()
        if data.get('error'):
            raise RuntimeError(f'openrouter error: {str(data["error"])[:300]}')
        choice = data['choices'][0]
        return choice['message'].get('content') or '', choice.get('finish_reason') or ''
    raise RuntimeError(f'openrouter still failing after retries: '
                       f'{last.status_code} {last.text[:200]}')


def _clean_settings_file(workdir: Path) -> Path:
    """Flag-settings that strip Claude Code's own context from the request:
    plugins, bundled skills, MCP, hooks, memory, git instructions. Verified to
    reduce harness overhead from ~36k tokens to ~30 (measured 2026-08-19)."""
    settings = {
        'disableBundledSkills': True, 'disableClaudeAiConnectors': True,
        'disableAllHooks': True, 'autoMemoryEnabled': False,
        'includeGitInstructions': False,
    }
    user_settings = Path.home() / '.claude' / 'settings.json'
    if user_settings.is_file():
        enabled = json.loads(user_settings.read_text(encoding='utf-8')).get('enabledPlugins') or {}
        settings['enabledPlugins'] = {name: False for name in enabled}
    f = workdir / 'clean-settings.json'
    f.write_text(json.dumps(settings), encoding='utf-8')
    return f


def _call_claude_code(system: str, messages: list[dict], workdir: Path, settings: Path,
                      model: str = MODEL) -> tuple[str, str]:
    """One trial through `claude -p` — runs on the user's subscription, no API key.

    Multi-turn continuations are flattened into a single prompt (claude -p is
    single-shot); rows record backend so results are never mixed across backends.
    """
    import os
    import shutil
    import subprocess
    import uuid
    exe = shutil.which('claude')
    if not exe:
        raise RuntimeError('claude CLI not found on PATH')
    prompt = '\n\n'.join(
        (m['content'] if m['role'] == 'user' else f'[Your previous reply]: {m["content"]}')
        for m in messages)
    # system prompt goes via file: Windows caps argv length far below big prompts
    sys_file = workdir / f'system-{uuid.uuid4().hex}.txt'
    sys_file.write_text(system, encoding='utf-8')
    try:
        p = subprocess.run(
            [exe, '-p', prompt, '--system-prompt-file', str(sys_file), '--tools', '',
             '--no-session-persistence', '--output-format', 'json', '--model', model,
             '--settings', str(settings), '--strict-mcp-config',
             '--exclude-dynamic-system-prompt-sections'],
            cwd=workdir, capture_output=True, text=True, encoding='utf-8', timeout=600)
    finally:
        os.unlink(sys_file)
    if p.returncode != 0:
        raise RuntimeError(f'claude -p failed: {p.stderr.strip()[:300]}')
    data = json.loads(p.stdout)
    if data.get('is_error'):
        raise RuntimeError(f'claude -p error result: {str(data)[:300]}')
    return data['result'], data.get('stop_reason') or 'end_turn'


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def run(exp: str, out: Path, dry_run: bool, yes: bool, seed: int,
        backend: str = 'auto', limit: int = 0, workers: int = 4,
        model: str | None = None) -> int:
    if backend == 'auto':
        import os
        backend = 'api' if os.environ.get('ANTHROPIC_API_KEY') else 'claude-code'
    model = model or MODEL
    trials = {'exp1': exp1_trials, 'exp2': exp2_trials, 'exp3': exp3_trials}[exp](seed)
    done = set()
    if out.exists():
        done = {json.loads(line)['trial_id'] for line in out.read_text(encoding='utf-8').splitlines() if line}
    todo = [t for t in trials if t.trial_id not in done]
    if limit:
        todo = todo[:limit]
    print(f'{exp}: {len(trials)} trials, {len(done)} done, {len(todo)} to run')

    tmp = Path(tempfile.mkdtemp(prefix='deskill-bench-'))
    build_project(tmp, all_domains())
    sets = nested_sets(seed)
    by_name = {d.name: d for d in all_domains()}

    def block_for(trial: Trial) -> str:
        if trial.exp in ('exp1', 'exp3'):
            names = [d.name for d in sets[trial.n]]
        else:  # installed: the checkable target among 24 distractors
            names = [trial.target] + [d.name for d in distractors()[:24]]
        random.Random(trial.order_seed).shuffle(names)
        return render_block(tmp, names)

    pads = {}

    def pad_for(trial: Trial) -> str:
        if trial.pad_k not in pads:
            pads[trial.pad_k] = transcript(trial.pad_k * 1000, seed)
        return pads[trial.pad_k]

    # cost gate
    est_in = est_out = 0
    for t in todo:
        est_in += _estimate_tokens(block_for(t)) + 300 + t.pad_k * 1000
        est_out += 400
        if t.condition == 'installed':
            est_in += _estimate_tokens(block_for(t)) + 400  # possible stage 2
    if backend == 'api':
        cost = est_in / 1e6 * PRICE_IN + est_out / 1e6 * PRICE_OUT
        print(f'estimated worst-case: ~{est_in:,} in / ~{est_out:,} out tokens ≈ ${cost:.2f} ({model}, api backend)')
    elif backend == 'openrouter':
        prices = _openrouter_prices(model)
        cost = (f'≈ ${est_in / 1e6 * prices[0] + est_out / 1e6 * prices[1]:.2f} '
                f'(catalog rates, before provider prompt-cache discounts)'
                if prices else '(catalog pricing unavailable)')
        print(f'backend openrouter ({model}): ~{est_in:,} in / ~{est_out:,} out tokens {cost}')
    else:
        print(f'backend claude-code: ~{est_in:,} in / ~{est_out:,} out tokens of your '
              f'Claude Code subscription quota ({model}); no API key needed')
    if exp == 'exp3':
        print('exp3 note: the system prompt is identical within each pad level, so '
              'after one cache-warming call per level the rest read from prompt '
              'cache (~10% of face value); the raw estimate above is the no-cache ceiling')
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

    if backend == 'api':
        import anthropic
        client = anthropic.Anthropic()

        def call(system, messages, max_tokens):
            return _call_api(client, system, messages, max_tokens, model)
    elif backend == 'openrouter':
        key = _resolve_openrouter_key()

        def call(system, messages, max_tokens):
            return _call_openrouter(system, messages, max_tokens, model, key)
    else:
        settings = _clean_settings_file(tmp)
        cc_cwd = tmp / 'cwd'
        cc_cwd.mkdir(exist_ok=True)

        def call(system, messages, max_tokens):
            return _call_claude_code(system, messages, cc_cwd, settings, model)

    # Payloads precompute sequentially: render_block rewrites one shared
    # .autotrigger file, so it must not run from worker threads.
    def payload(t: Trial) -> tuple:
        if t.exp == 'exp3':
            return (padded_system(block_for(t), pad_for(t)),
                    [{'role': 'user', 'content': trigger_user_message(t.task)}])
        if t.exp == 'exp1' or t.condition == 'installed':
            return (installed_system(block_for(t)),
                    [{'role': 'user', 'content': trigger_user_message(t.task)}])
        return BASE_SYSTEM, referenced_messages(by_name[t.target].body, t.task)

    def process(t: Trial, system: str, messages: list[dict]) -> dict:
        row = {'trial_id': t.trial_id, 'exp': t.exp, 'target': t.target,
               'paraphrase_idx': t.paraphrase_idx, 'n': t.n, 'condition': t.condition,
               'pad_k': t.pad_k, 'backend': backend, 'model': model}
        try:
            if t.exp in ('exp1', 'exp3') or t.condition == 'installed':
                reply, stop = call(system, messages, 512 if t.exp != 'exp2' else 1024)
                predicted = parse_load(reply)
                row.update(predicted=predicted, triggered=predicted == t.target,
                           stop_reason=stop)
                if t.exp == 'exp2':
                    if predicted == t.target:
                        messages = messages + loaded_continuation(
                            reply.strip(), by_name[t.target].body)
                        reply, _ = call(system, messages, 1024)
                    row.update(reply=reply, success=by_name[t.target].checker(reply))
            else:  # referenced
                reply, stop = call(system, messages, 1024)
                row.update(reply=reply, stop_reason=stop,
                           success=by_name[t.target].checker(reply))
        except Exception as e:  # record and continue — reruns resume past done rows
            row.update(error=f'{type(e).__name__}: {e}')
        return row

    from concurrent.futures import ThreadPoolExecutor, as_completed
    payloads = [(t, *payload(t)) for t in todo]
    out.parent.mkdir(parents=True, exist_ok=True)
    counter = [0]
    with out.open('a', encoding='utf-8') as f:

        def execute(batch, nworkers):
            with ThreadPoolExecutor(max_workers=nworkers) as pool:
                futures = {pool.submit(process, t, s, m): t for t, s, m in batch}
                for fut in as_completed(futures):
                    row = fut.result()  # rows are written from this thread only
                    f.write(json.dumps(row) + '\n')
                    f.flush()
                    counter[0] += 1
                    print(f'[{counter[0]}/{len(todo)}] {row["trial_id"]}: '
                          f'{row.get("error") or row.get("success", row.get("triggered"))}')

        if exp == 'exp3':
            # one warm-up call per pad level writes the prompt cache; the rest read it
            for pad_k in sorted({t.pad_k for t, _, _ in payloads}):
                level = [p for p in payloads if p[0].pad_k == pad_k]
                execute(level[:1], 1)
                execute(level[1:], workers)
        else:
            execute(payloads, workers)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='deskill-bench')
    p.add_argument('exp', choices=['exp1', 'exp2', 'exp3'])
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--seed', type=int, default=7)
    p.add_argument('--backend', choices=['auto', 'api', 'claude-code', 'openrouter'],
                   default='auto',
                   help='api = Anthropic SDK (needs ANTHROPIC_API_KEY); '
                        'claude-code = headless `claude -p` on your subscription; '
                        'openrouter = any catalog model (OPENROUTER_API_KEY or .env); '
                        'auto = api if a key is set, else claude-code')
    p.add_argument('--model', default=None,
                   help=f'model id (default {MODEL}); openrouter ids look like '
                        'openai/gpt-5.6-terra or deepseek/deepseek-v4-pro-0813')
    p.add_argument('--limit', type=int, default=0, help='run at most N trials (smoke tests)')
    p.add_argument('--workers', type=int, default=4,
                   help='parallel trials (ponytail: modest default — subscription rate limits)')
    a = p.parse_args(argv)
    slug = (a.model or MODEL).split('/')[-1]
    default_name = f'{a.exp}.jsonl' if (a.model or MODEL) == MODEL else f'{a.exp}-{slug}.jsonl'
    out = a.out or Path('evals/results') / default_name
    return run(a.exp, out, a.dry_run, a.yes, a.seed, a.backend, a.limit, a.workers, a.model)


if __name__ == '__main__':
    sys.exit(main())
