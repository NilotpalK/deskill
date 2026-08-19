"""Offline tests for deskill-bench — generators, conditions, parsing, analysis.

No API calls anywhere in this file.
"""
import json

from evals.bench.analyze import wilson
from evals.bench.conditions import (
    installed_system, parse_load, referenced_messages, trigger_user_message,
)
from evals.bench.domains import CHECKABLE, TARGETS, all_domains
from evals.bench.runner import exp1_trials, exp2_trials
from evals.bench.skills_gen import build_project, nested_sets, render_block

from deskill.core import Options


def test_domain_pool_size_and_uniqueness():
    pool = all_domains()
    names = [d.name for d in pool]
    assert len(names) == len(set(names))
    assert len(pool) >= 120
    assert len(TARGETS) == 10 and len(CHECKABLE) == 10
    for d in TARGETS + CHECKABLE:
        assert len(d.task_paraphrases) >= 3
        assert d.description.startswith('Use when')


def test_checkers_accept_good_and_reject_bad():
    for d in CHECKABLE:
        assert d.checker(d.good_example), d.name
        assert not d.checker('I cannot help with that.'), d.name


def test_nested_sets_are_nested_and_sized():
    sets = nested_sets(seed=7)
    assert sorted(sets) == [10, 25, 50, 100]
    for n, domains in sets.items():
        assert len(domains) == n
    names = {n: {d.name for d in ds} for n, ds in sets.items()}
    assert names[10] <= names[25] <= names[50] <= names[100]
    assert names[10] == {d.name for d in TARGETS}


def test_build_project_and_render_block(tmp_path):
    sets = nested_sets(seed=7)
    build_project(tmp_path, sets[25])
    block = render_block(tmp_path, [d.name for d in sets[25]])
    assert block.startswith('Auto-triggered Skills')
    for d in sets[25]:
        assert f'(.atskills/{d.name}/SKILL.md)' in block
    # order follows the given name order
    order = [d.name for d in sets[25]]
    positions = [block.index(f'/{name}/SKILL.md') for name in order]
    assert positions == sorted(positions)


def test_render_block_order_respects_shuffle(tmp_path):
    sets = nested_sets(seed=7)
    build_project(tmp_path, sets[10])
    names = [d.name for d in sets[10]]
    rev = list(reversed(names))
    block = render_block(tmp_path, rev)
    positions = [block.index(f'/{name}/SKILL.md') for name in rev]
    assert positions == sorted(positions)


def test_parse_load():
    assert parse_load('LOAD(pdf-form-filling)\n') == 'pdf-form-filling'
    assert parse_load('Sure!\nLOAD(.atskills/x/SKILL.md)') == 'x'
    assert parse_load('LOAD(.atskills/team/deploy/SKILL.md) rest') == 'team/deploy'
    assert parse_load('No skill applies here.') is None
    # mangled-prefix spellings are selection successes, not errors
    assert parse_load('LOAD(./atskills/pdf-form-filling)') == 'pdf-form-filling'
    assert parse_load('LOAD(atskills/dockerfile-slimming)') == 'dockerfile-slimming'
    assert parse_load('LOAD(./.atskills/i18n-string-extraction)') == 'i18n-string-extraction'
    assert parse_load('LOAD(`sec-check`)') == 'sec-check'


def test_condition_builders():
    sys_prompt = installed_system('Auto-triggered Skills (...):\n- x: y (.atskills/x/SKILL.md)')
    assert 'LOAD(' in sys_prompt and 'Auto-triggered Skills' in sys_prompt
    user = trigger_user_message('Fill this PDF form for me')
    assert 'Fill this PDF' in user
    msgs = referenced_messages('BODY RULE TEXT', 'do the task')
    assert msgs[-1]['role'] == 'user'
    content = msgs[-1]['content']
    assert content.index('BODY RULE TEXT') < content.index('do the task')


def test_exp1_trials_deterministic_and_covering():
    a = exp1_trials(seed=7)
    b = exp1_trials(seed=7)
    assert [t.trial_id for t in a] == [t.trial_id for t in b]
    assert len(a) == 10 * 3 * 4          # targets x paraphrases x N-conditions
    assert len({t.trial_id for t in a}) == len(a)
    assert {t.n for t in a} == {10, 25, 50, 100}


def test_exp2_trials_shape():
    trials = exp2_trials(seed=7)
    assert len(trials) == 10 * 3 * 2     # checkable x paraphrases x conditions
    assert {t.condition for t in trials} == {'installed', 'referenced'}


def test_wilson_interval():
    lo, hi = wilson(8, 10)
    assert 0 < lo < 0.8 < hi < 1
    assert wilson(0, 0) == (0.0, 1.0)


def test_padding_transcript_sized_and_deterministic():
    from evals.bench.padding import transcript
    for k in (25_000, 100_000):
        text = transcript(k, seed=7)
        assert abs(len(text) / 4 - k) / k < 0.05      # within 5% of requested tokens
    assert transcript(25_000, seed=7) == transcript(25_000, seed=7)
    assert transcript(25_000, seed=7) != transcript(25_000, seed=8)


def test_padding_cannot_plausibly_trigger_targets():
    from evals.bench.padding import transcript
    text = transcript(50_000, seed=7).lower()
    for d in TARGETS + CHECKABLE:
        assert d.name not in text
    for keyword in ('pdf', 'commit', 'aws', 'dockerfile', 'csv', 'changelog',
                    'migration', 'standup', 'release notes', 'on-call'):
        assert keyword not in text, keyword


def test_exp3_trials_shape_and_cache_friendliness():
    from evals.bench.runner import exp3_trials
    trials = exp3_trials(seed=7)
    assert len(trials) == 10 * 3 * 3                 # targets x paraphrases x pad levels
    assert {t.pad_k for t in trials} == {25, 50, 100}
    assert all(t.n == 100 for t in trials)
    for pad in (25, 50, 100):
        level = [t for t in trials if t.pad_k == pad]
        assert len({t.order_seed for t in level}) == 1   # one block order per level → cacheable
    assert exp3_trials(seed=7)[0].trial_id == exp3_trials(seed=7)[0].trial_id


def test_padded_system_ordering():
    from evals.bench.conditions import padded_system
    sys_prompt = padded_system('Auto-triggered Skills (X):\n- x: y (.atskills/x/SKILL.md)',
                               'PADDING CONTENT HERE')
    assert (sys_prompt.index('Auto-triggered Skills')
            < sys_prompt.index('LOAD(')
            < sys_prompt.index('PADDING CONTENT HERE'))


def test_exp4_trials_shape():
    from evals.bench.runner import exp4_trials
    trials = exp4_trials(seed=7)
    assert len(trials) == 10 * 3 * 2
    assert {t.condition for t in trials} == {'referenced', 'bare'}
    assert len({t.trial_id for t in trials}) == len(trials)


def test_exp5_pool_and_trials():
    from evals.bench.domains import SIBLINGS, exp5_pool
    from evals.bench.runner import exp5_trials
    pool = exp5_pool()
    names = [d.name for d in pool]
    assert len(pool) == 50 and len(set(names)) == 50
    for t in TARGETS:
        assert t.name in names
        for s in SIBLINGS[t.name]:
            assert s.name in names and s.description.startswith('Use when')
    trials = exp5_trials(seed=7)
    assert len(trials) == 30 and all(t.n == 50 for t in trials)


def test_report_exp5_splits_sibling_confusion():
    from evals.bench.analyze import report_exp5
    rows = [
        {'exp': 'exp5', 'target': 'pdf-form-filling', 'predicted': 'pdf-form-filling',
         'triggered': True, 'model': 'm'},
        {'exp': 'exp5', 'target': 'pdf-form-filling', 'predicted': 'pdf-text-ocr',
         'triggered': False, 'model': 'm'},
        {'exp': 'exp5', 'target': 'pdf-form-filling', 'predicted': 'kafka-debugging',
         'triggered': False, 'model': 'm'},
        {'exp': 'exp5', 'target': 'pdf-form-filling', 'predicted': None,
         'triggered': False, 'model': 'm'},
    ]
    out = report_exp5(rows)
    assert 'exact correct skill | 1/4' in out
    assert 'confused with a sibling | 1/4' in out
    assert 'other wrong skill | 1/4' in out
    assert 'no trigger | 1/4' in out


def test_report_exp3_groups_by_pad():
    from evals.bench.analyze import report_exp3
    rows = ([{'exp': 'exp3', 'pad_k': 25, 'triggered': True, 'predicted': 'x', 'target': 'x'}] * 3
            + [{'exp': 'exp3', 'pad_k': 100, 'triggered': False, 'predicted': None, 'target': 'x'}] * 2)
    out = report_exp3(rows)
    assert '~25k | 3/3' in out and '~100k | 0/2' in out
