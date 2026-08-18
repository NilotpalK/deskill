from deskill.cli import main

from tests.conftest import make_local_skill


def run(project, *argv, monkeypatch, capsys):
    monkeypatch.chdir(project.working_dir)
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_get_local(project, monkeypatch, capsys):
    make_local_skill(project, 'my-tdd', 'How we do TDD')
    code, out, _ = run(project, 'get', 'my-tdd', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and 'How we do TDD' in out


def test_get_miss_is_exit_1_stderr(project, monkeypatch, capsys):
    code, out, err = run(project, 'get', 'nope', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 1 and out == '' and '.atskills/nope' in err


def test_triggers_add_list_remove(project, monkeypatch, capsys):
    make_local_skill(project, 'alpha')
    code, _, _ = run(project, 'triggers', 'add', 'alpha', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0
    code, out, _ = run(project, 'triggers', 'list', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and 'alpha' in out
    code, _, _ = run(project, 'triggers', 'remove', 'alpha', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0
    code, out, _ = run(project, 'triggers', 'list', monkeypatch=monkeypatch, capsys=capsys)
    assert 'alpha' not in out


def test_prompt_outputs_block_and_token_count(project, monkeypatch, capsys):
    make_local_skill(project, 'sec-check', 'Reviews security')
    run(project, 'triggers', 'add', 'sec-check', monkeypatch=monkeypatch, capsys=capsys)
    code, out, err = run(project, 'prompt', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0
    assert out.startswith('Auto-triggered Skills (.atskills/.autotrigger):')
    assert 'sec-check: Reviews security' in out
    assert 'tokens' in err        # count goes to stderr — stdout stays spliceable


def test_prompt_empty_is_empty_stdout(project, monkeypatch, capsys):
    code, out, _ = run(project, 'prompt', monkeypatch=monkeypatch, capsys=capsys)
    assert code == 0 and out == ''
