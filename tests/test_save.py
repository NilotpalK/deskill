import re

from deskill.core.ids import disk_path
from deskill.core.save import save

from tests.conftest import SKILL_V1


def dest_of(project, id):
    return project.working_dir / '.atskills' / disk_path(id)


def test_save_lands_with_two_line_source(project, remotes):
    sha = remotes('acme', 'skills', {'mine/SKILL.md': SKILL_V1})
    r = save('gh:acme/skills/mine', project)
    assert r.success, r.error
    d = dest_of(project, 'gh:acme/skills/mine')
    assert (d / 'SKILL.md').read_text(encoding='utf-8') == SKILL_V1
    line1, line2 = (d / '.source').read_text(encoding='utf-8').strip().split('\n')
    assert line1 == 'gh:acme/skills/mine'
    assert re.match(r'^\d{4}-\d{2}-\d{2} rev:' + sha + '$', line2)


def test_resave_replaces_unedited(project, remotes):
    remotes('acme', 'again', {'mine/SKILL.md': SKILL_V1})
    save('gh:acme/again/mine', project)
    v2 = SKILL_V1.replace('v1', 'v2')
    sha_b = remotes('acme', 'again', {'mine/SKILL.md': v2})
    r = save('gh:acme/again/mine', project)
    assert r.success, r.error
    d = dest_of(project, 'gh:acme/again/mine')
    assert (d / 'SKILL.md').read_text(encoding='utf-8') == v2
    assert f'rev:{sha_b}' in (d / '.source').read_text(encoding='utf-8')


def test_resave_edited_is_conflict_nothing_touched(project, remotes):
    remotes('acme', 'edited', {'mine/SKILL.md': SKILL_V1})
    save('gh:acme/edited/mine', project)
    d = dest_of(project, 'gh:acme/edited/mine')
    mine = SKILL_V1 + '\nhouse rules\n'
    (d / 'SKILL.md').write_text(mine, encoding='utf-8')
    remotes('acme', 'edited', {'mine/SKILL.md': SKILL_V1.replace('v1', 'v3')})
    r = save('gh:acme/edited/mine', project)
    assert not r.success and 'conflict' in r.error
    assert (d / 'SKILL.md').read_text(encoding='utf-8') == mine


def test_cap_on_save_path_is_a_verdict(project, remotes):
    files = {f'skills/s{i:03d}/SKILL.md': f'---\nname: s{i}\ndescription: d\n---\nb\n'
             for i in range(130)}
    remotes('mega', 'catalog', files)
    r = save('gh:mega/catalog', project)
    assert not r.success and '130 skills' in r.error
    root = project.working_dir / '.atskills'
    assert [n for n in (p.name for p in root.iterdir()) if not n.startswith('.')] == []


def test_parent_save_absorbs_unedited_children(project, remotes):
    remotes('acme', 'nest', {
        'skills/alpha/SKILL.md': '---\nname: alpha\ndescription: a\n---\nb\n',
        'skills/beta/SKILL.md': '---\nname: beta\ndescription: b\n---\nb\n',
    })
    assert save('gh:acme/nest/skills/alpha', project).success
    r = save('gh:acme/nest/skills', project)
    assert r.success, r.error
    assert 'superset' in r.warning
    d = dest_of(project, 'gh:acme/nest/skills')
    assert (d / '.source').exists()
    assert not (d / 'alpha' / '.source').exists()     # child stamp replaced
    assert (d / 'alpha' / 'SKILL.md').exists() and (d / 'beta' / 'SKILL.md').exists()


def test_parent_save_refuses_edited_child_and_names_it(project, remotes):
    remotes('acme', 'nest2', {
        'skills/alpha/SKILL.md': '---\nname: alpha\ndescription: a\n---\nb\n',
        'skills/beta/SKILL.md': '---\nname: beta\ndescription: b\n---\nb\n',
    })
    save('gh:acme/nest2/skills/alpha', project)
    child = dest_of(project, 'gh:acme/nest2/skills/alpha') / 'SKILL.md'
    child.write_text(child.read_text(encoding='utf-8') + '\nhouse rules\n', encoding='utf-8')
    r = save('gh:acme/nest2/skills', project)
    assert not r.success and 'edited saved skill' in r.error and 'alpha' in r.error
    assert 'house rules' in child.read_text(encoding='utf-8')


def test_huge_bundle_single_skill_never_refused(project, remotes):
    files = {'solo/SKILL.md': '---\nname: solo\ndescription: one\n---\nb\n'}
    files.update({f'solo/references/r{i}.md': f'ref {i}' for i in range(200)})
    remotes('mega', 'bundle', files)
    r = save('gh:mega/bundle/solo', project)
    assert r.success, r.error
    assert (dest_of(project, 'gh:mega/bundle/solo') / 'references' / 'r0.md').exists()


def test_save_local_id_is_an_error(project):
    r = save('deploy', project)
    assert not r.success
    assert 'already' in r.error.lower() or 'local' in r.error.lower()
