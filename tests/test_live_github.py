import shutil
import socket

import pytest

from deskill.core import Options, resolve


def _online():
    try:
        socket.create_connection(('github.com', 443), timeout=5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not shutil.which('git') or not _online(), reason='needs git + network')


def test_resolve_anthropics_pdf_skill(tmp_path):
    (tmp_path / '.atskills').mkdir()
    opts = Options(working_dir=tmp_path, cache_dir=tmp_path / '.cache')
    r = resolve('gh:anthropics/skills/skills/pdf', opts)
    assert r.success, r.error
    assert r.kind == 'skill'
    assert 'name:' in r.content and 'pdf' in r.content.lower()
    # second resolve revalidates: cache hit, still succeeds
    assert resolve('gh:anthropics/skills/skills/pdf', opts).source in ('cache', 'fresh')


def test_menu_of_anthropics_skills(tmp_path):
    (tmp_path / '.atskills').mkdir()
    opts = Options(working_dir=tmp_path, cache_dir=tmp_path / '.cache')
    r = resolve('gh:anthropics/skills/skills', opts)
    assert r.success, r.error
    assert r.kind == 'menu'
    assert 'gh:anthropics/skills/skills/pdf:' in r.content
