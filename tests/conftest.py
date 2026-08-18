import subprocess
from pathlib import Path

import pytest

from deskill.core.resolve import Options


def _git(cwd, *args):
    return subprocess.run(
        ['git', '-c', 'user.email=t@t', '-c', 'user.name=t',
         '-c', 'commit.gpgsign=false', *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def remotes(tmp_path_factory):
    base = tmp_path_factory.mktemp('remotes')

    def make(owner, repo, files):
        d = base / owner / f'{repo}.git'
        if not d.exists():
            d.mkdir(parents=True)
            _git(d, 'init', '-q', '-b', 'main')
            # What GitHub's servers allow, ours allows: filters and by-sha fetches.
            _git(d, 'config', 'uploadpack.allowFilter', 'true')
            _git(d, 'config', 'uploadpack.allowAnySHA1InWant', 'true')
        for rel, content in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
        _git(d, 'add', '-A')
        _git(d, 'commit', '-q', '-m', 'update', '--allow-empty')
        return _git(d, 'rev-parse', 'HEAD')

    make.base_url = base.as_uri()  # file:///... — remote_url appends .git
    return make


@pytest.fixture
def project(tmp_path, remotes):
    (tmp_path / '.atskills').mkdir()
    return Options(working_dir=tmp_path, cache_dir=tmp_path / '.cache',
                   github_base_url=remotes.base_url)


def make_local_skill(opts, rel, description=None):
    d = opts.working_dir / '.atskills' / rel
    d.mkdir(parents=True, exist_ok=True)
    name = rel.split('/')[-1]
    (d / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {description or "does " + rel}\n---\nbody\n',
        encoding='utf-8')
    return d


SKILL_V1 = '---\nname: mine\ndescription: v1\n---\nv1 body\n'
