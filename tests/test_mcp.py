import asyncio

import deskill.mcp_server as srv

from tests.conftest import make_local_skill


def test_tools_registered():
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == {
        'deskill_get', 'deskill_menu', 'deskill_save',
        'deskill_install', 'deskill_uninstall', 'deskill_prompt',
    }


def test_get_and_prompt_roundtrip(project, monkeypatch):
    monkeypatch.chdir(project.working_dir)
    make_local_skill(project, 'my-tdd', 'How we do TDD')
    assert 'How we do TDD' in srv.get_impl('my-tdd')
    assert 'never leaves the machine' in srv.get_impl('missing')  # error as readable string
    assert 'added' in srv.install_impl('my-tdd')
    assert 'my-tdd: How we do TDD' in srv.prompt_impl()
    assert 'removed' in srv.uninstall_impl('my-tdd')
    assert srv.prompt_impl().startswith('No skills auto-trigger')


def test_install_refuses_missing_frontmatter(project, monkeypatch):
    monkeypatch.chdir(project.working_dir)
    d = project.working_dir / '.atskills' / 'broken'
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text('---\nname: broken\n---\nno description', encoding='utf-8')
    out = srv.install_impl('broken')
    assert 'frontmatter' in out
    assert not (project.working_dir / '.atskills' / '.autotrigger').exists()


def test_menu_impl(project, monkeypatch):
    monkeypatch.chdir(project.working_dir)
    make_local_skill(project, 'team/deploy', 'Ship it')
    assert 'team/deploy: Ship it' in srv.menu_impl('team')
