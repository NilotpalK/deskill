from deskill.core.resolve import resolve

from tests.conftest import make_local_skill, SKILL_V1


def test_local_first_by_path(project):
    make_local_skill(project, 'my-tdd', 'How we do TDD')
    r = resolve('my-tdd', project)
    assert r.success and r.kind == 'skill' and r.source == 'local'
    assert 'How we do TDD' in r.content


def test_bare_path_never_reaches_network(project):
    r = resolve('someone/elses-skill', project)
    assert not r.success
    assert '.atskills/someone/elses-skill' in r.error   # says where it looked
    assert 'hub:owner/name' in r.error and 'gh:owner/repo/path' in r.error
    for word in ['HTTP', 'ECONN', 'registry', 'fetches from']:
        assert word.lower() not in r.error.lower()


def test_saved_copy_answers_its_own_gh_address(project):
    make_local_skill(project, 'gh/acme/skills/mine', 'vendored copy')
    r = resolve('gh:acme/skills/mine', project)      # no remote exists at all
    assert r.success and r.source == 'local' and 'vendored copy' in r.content


def test_validating_cache(project, remotes):
    remotes('acme', 'skills', {'mine/SKILL.md': SKILL_V1})
    first = resolve('gh:acme/skills/mine', project)
    assert first.success and first.source == 'fresh'
    # marker survives an unchanged revalidation (a re-download would erase it)
    (first.path / 'SKILL.md').write_text(first.content + 'CACHE-MARKER\n', encoding='utf-8')
    hit = resolve('gh:acme/skills/mine', project)
    assert hit.source == 'cache' and 'CACHE-MARKER' in hit.content
    remotes('acme', 'skills', {'mine/SKILL.md': SKILL_V1.replace('v1', 'v2')})
    fresh = resolve('gh:acme/skills/mine', project)
    assert fresh.source == 'fresh' and 'v2' in fresh.content


def test_offline_serves_stale(project, remotes):
    remotes('acme', 'skills', {'mine/SKILL.md': SKILL_V1})
    assert resolve('gh:acme/skills/mine', project).success
    dead = type(project)(working_dir=project.working_dir, cache_dir=project.cache_dir,
                         github_base_url='file:///nonexistent-remotes')
    r = resolve('gh:acme/skills/mine', dead)
    assert r.success and r.source == 'stale'
    r2 = resolve('gh:acme/skills/other', dead)       # nothing cached → fail with why
    assert not r2.success and 'unreachable' in r2.error.lower()


def test_directory_is_a_menu(project, remotes):
    remotes('acme', 'kit', {
        'skills/deploy/SKILL.md': '---\nname: deploy\ndescription: Ship it\n---\nb\n',
        'skills/review/SKILL.md': '---\nname: review\ndescription: Check it\n---\nb\n',
    })
    r = resolve('gh:acme/kit/skills', project)
    assert r.success and r.kind == 'menu'
    assert 'gh:acme/kit/skills/deploy: Ship it' in r.content
    assert 'gh:acme/kit/skills/review: Check it' in r.content


def test_cap_refuses_before_download_with_suggestions(project, remotes):
    files = {f'bundles/b{i % 13}/s{i:03d}/SKILL.md':
             f'---\nname: s{i}\ndescription: d\n---\nb\n' for i in range(130)}
    remotes('mega', 'catalog', files)
    r = resolve('gh:mega/catalog', project)
    assert not r.success
    assert '130 skills' in r.error and 'gh:mega/catalog/bundles/b' in r.error


def test_local_menu(project):
    make_local_skill(project, 'team/deploy', 'Ship it')
    make_local_skill(project, 'team/review', 'Check it')
    r = resolve('team', project)
    assert r.kind == 'menu'
    assert 'team/deploy: Ship it' in r.content and 'team/review: Check it' in r.content


def test_hub_is_a_stub(project):
    r = resolve('hub:acme/thing', project)
    assert not r.success and 'hub' in r.error


def test_invalid_id_is_an_error_value(project):
    r = resolve('../etc/passwd', project)
    assert not r.success and r.kind == 'error'
