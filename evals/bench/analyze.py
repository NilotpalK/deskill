"""Turn bench JSONL into the paper-facing tables. Stdlib only.

Usage: python -m evals.bench.analyze evals/results/exp1.jsonl [evals/results/exp2.jsonl ...]
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _rows(path: Path) -> list[dict]:
    from .domains import CHECKABLE
    checkers = {d.name: d.checker for d in CHECKABLE}
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
    for r in rows:  # re-score from the stored reply: checker fixes never re-spend
        if 'reply' in r and r['target'] in checkers:
            r['success'] = checkers[r['target']](r['reply'])
    return rows


def _fmt(k: int, n: int) -> str:
    if n == 0:
        return '—'
    lo, hi = wilson(k, n)
    return f'{k}/{n} = {k / n:.0%} [{lo:.0%}–{hi:.0%}]'


def report_exp1(rows: list[dict]) -> str:
    ok = [r for r in rows if 'error' not in r]
    by_n = defaultdict(list)
    for r in ok:
        by_n[r['n']].append(r)
    model = rows[0].get('model', '') if rows else ''
    lines = [f'## Experiment 1 — trigger rate vs. installed-skill count ({model})',
             '', '| N | correct trigger | wrong skill | no trigger |', '|---|---|---|---|']
    for n in sorted(by_n):
        rs = by_n[n]
        correct = sum(1 for r in rs if r.get('triggered'))
        wrong = sum(1 for r in rs if r.get('predicted') and not r.get('triggered'))
        none_ = sum(1 for r in rs if not r.get('predicted'))
        lines.append(f'| {n} | {_fmt(correct, len(rs))} | {wrong}/{len(rs)} | {none_}/{len(rs)} |')
    if len(ok) != len(rows):
        lines.append(f'\n({len(rows) - len(ok)} error rows excluded)')
    return '\n'.join(lines)


def report_exp3(rows: list[dict]) -> str:
    ok = [r for r in rows if 'error' not in r]
    by_pad = defaultdict(list)
    for r in ok:
        by_pad[r.get('pad_k', 0)].append(r)
    model = rows[0].get('model', '') if rows else ''
    lines = [f'## Experiment 3 — trigger rate vs. context padding (N=100 installed, {model})',
             '', '| transcript tokens between block and task | correct trigger | wrong skill | no trigger |',
             '|---|---|---|---|']
    for pad in sorted(by_pad):
        rs = by_pad[pad]
        correct = sum(1 for r in rs if r.get('triggered'))
        wrong = sum(1 for r in rs if r.get('predicted') and not r.get('triggered'))
        none_ = sum(1 for r in rs if not r.get('predicted'))
        lines.append(f'| ~{pad}k | {_fmt(correct, len(rs))} | {wrong}/{len(rs)} | {none_}/{len(rs)} |')
    lines.append('\n(0-padding baseline: experiment 1, N=100 row)')
    if len(ok) != len(rows):
        lines.append(f'({len(rows) - len(ok)} error rows excluded)')
    return '\n'.join(lines)


def report_exp2(rows: list[dict]) -> str:
    ok = [r for r in rows if 'error' not in r]
    by_cond = defaultdict(list)
    for r in ok:
        by_cond[r['condition']].append(r)
    lines = ['## Experiment 2 — install vs. point-of-use reference',
             '', '| condition | task success |', '|---|---|']
    for cond in ('installed', 'referenced'):
        rs = by_cond.get(cond, [])
        lines.append(f'| {cond} | {_fmt(sum(1 for r in rs if r.get("success")), len(rs))} |')
    lines += ['', '| skill | installed | referenced |', '|---|---|---|']
    by_skill = defaultdict(lambda: defaultdict(list))
    for r in ok:
        by_skill[r['target']][r['condition']].append(r)
    for skill in sorted(by_skill):
        cells = []
        for cond in ('installed', 'referenced'):
            rs = by_skill[skill][cond]
            cells.append(_fmt(sum(1 for r in rs if r.get('success')), len(rs)))
        lines.append(f'| {skill} | {cells[0]} | {cells[1]} |')
    inst = by_cond.get('installed', [])
    trig = sum(1 for r in inst if r.get('triggered'))
    if inst:
        lines.append(f'\ninstalled-condition trigger rate (N=25): {_fmt(trig, len(inst))}')
    return '\n'.join(lines)


def main(argv=None) -> int:
    paths = [Path(p) for p in (argv or sys.argv[1:])]
    if not paths:
        print(__doc__)
        return 1
    for path in paths:
        rows = _rows(path)
        exp = rows[0]['exp'] if rows else path.stem
        report = {'exp1': report_exp1, 'exp2': report_exp2, 'exp3': report_exp3}
        print(report.get(exp, report_exp1)(rows))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
