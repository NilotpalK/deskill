from deskill.core.autotrigger import (
    add_trigger_line, expand_local_triggers, has_trigger_line,
    parse_triggers, remove_trigger_line,
)


def root_of(project):
    return project.working_dir / '.atskills'


def write_at(project, text):
    (root_of(project) / '.autotrigger').write_text(text, encoding='utf-8')


def skill(project, rel, name):
    d = root_of(project) / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: about {name}\n---\nbody of {name}\n',
        encoding='utf-8')


def test_parse_gitignore_semantics(project):
    write_at(project, '# comment only\nalpha\n\nalpha\n@gh:acme/skills/deploy\nteam/  \n')
    entries = parse_triggers(root_of(project))
    assert [e.line for e in entries] == ['alpha', '@gh:acme/skills/deploy', 'team/']
    assert entries[1].cloud is True and entries[2].cloud is False


def test_hash_inside_pattern_is_literal(project):
    write_at(project, 'c#-patterns\n  # indented comment\n')
    assert [e.line for e in parse_triggers(root_of(project))] == ['c#-patterns']


def test_add_remove_round_trip_idempotent(project):
    r = root_of(project)
    assert add_trigger_line(r, 'alpha') is True
    assert add_trigger_line(r, 'alpha') is False
    assert has_trigger_line(r, 'alpha') is True
    assert remove_trigger_line(r, 'alpha') is True
    assert has_trigger_line(r, 'alpha') is False
    assert remove_trigger_line(r, 'alpha') is False


def test_expand_local_dir_saved_and_errors(project):
    r = root_of(project)
    skill(project, 'my-tdd', 'my-tdd')
    skill(project, 'team/deploy', 'deploy')
    skill(project, 'team/review', 'review')
    skill(project, 'gh/acme/skills/deploy', 'acme-deploy')
    (r / 'gh/acme/skills/deploy/.source').write_text(
        'gh:acme/skills/deploy\n2026-08-01 rev:abc123\n', encoding='utf-8')
    (r / 'broken').mkdir()
    (r / 'broken/SKILL.md').write_text('---\nname: broken\n---\nno description',
                                       encoding='utf-8')
    write_at(project,
             'my-tdd\nteam/\ngh/acme/skills/deploy\nbroken\nmissing-skill\n'
             '@gh:acme/skills/deploy\n')

    entries = expand_local_triggers(r)
    ok = [e for e in entries if not e.error]
    errs = [e for e in entries if e.error]
    assert sorted(e.fm['name'] for e in ok) == ['acme-deploy', 'deploy', 'my-tdd', 'review']
    acme = [e for e in ok if e.fm['name'] == 'acme-deploy']
    assert len(acme) == 1                     # saved copy answers its own @ line, once
    assert acme[0].where == 'saved' and acme[0].origin == 'gh:acme/skills/deploy'
    assert next(e for e in ok if e.fm['name'] == 'my-tdd').where == 'yours'
    assert len(errs) == 2
    assert 'frontmatter' in next(e for e in errs if e.line == 'broken').error
    assert 'matches nothing' in next(e for e in errs if e.line == 'missing-skill').error


def test_real_gitignore_globs_and_negation(project):
    skill(project, 'writing/commit-messages', 'commit-messages')
    skill(project, 'writing/drafts', 'drafts')
    skill(project, 'sec-checklist', 'sec-checklist')
    write_at(project, 'writing/*\n!writing/drafts\nsec-*\n')
    names = sorted(e.fm['name'] for e in expand_local_triggers(root_of(project))
                   if not e.error)
    assert names == ['commit-messages', 'sec-checklist']


def test_empty_expansion_is_a_value(project):
    assert expand_local_triggers(root_of(project)) == []
