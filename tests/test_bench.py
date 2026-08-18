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
