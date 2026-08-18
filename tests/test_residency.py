from deskill.core.residency import build_autotrigger_index, estimate_tokens

from tests.test_autotrigger import skill, write_at


def test_exact_block(project):
    skill(project, 'sec-check', 'sec-check')
    (project.working_dir / '.atskills/sec-check/SKILL.md').write_text(
        '---\nname: sec-check\ndescription: Reviews security\n---\nb\n', encoding='utf-8')
    write_at(project, 'sec-check\n')
    assert build_autotrigger_index(project) == (
        'Auto-triggered Skills (.atskills/.autotrigger):\n'
        '- sec-check: Reviews security (.atskills/sec-check/SKILL.md)'
    )


def test_empty_when_nothing_triggers(project):
    assert build_autotrigger_index(project) == ''


def test_token_estimate():
    assert estimate_tokens('') == 0 and estimate_tokens('abcd' * 25) == 25
