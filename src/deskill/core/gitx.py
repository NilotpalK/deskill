"""Git transport (PROTOCOL.md §5): shallow blob-filtered clones + ls-remote probes.

The reference transport is git itself — one negotiated round trip, no API quota,
private repos ride the user's git credentials, revisions come free.
"""
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


class GitError(Exception):
    pass


def git_available() -> bool:
    return shutil.which('git') is not None


def remote_url(base_url: str, owner: str, repo: str) -> str:
    return f'{base_url}/{owner}/{repo}.git'


def _run(args: list[str], cwd: str | Path | None = None) -> str:
    p = subprocess.run(['git', *args], cwd=cwd, capture_output=True,
                       text=True, encoding='utf-8', timeout=120)
    if p.returncode != 0:
        raise GitError(p.stderr.strip() or f'git {" ".join(args)} failed')
    return p.stdout


def _rmtree(path: str | Path) -> None:
    def _chmod_retry(fn, p, exc):  # git object files are read-only on Windows
        Path(p).chmod(stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=_chmod_retry)


def probe_head(url: str) -> str | None:
    """One revision probe: the sha of HEAD, or None when unreachable."""
    try:
        out = _run(['ls-remote', url, 'HEAD'])
    except (GitError, subprocess.TimeoutExpired):
        return None
    return out.split()[0] if out.split() else None


@contextmanager
def shallow_clone(url: str):
    """Yields (tmp_repo_dir, head_sha). Blob-filtered, no checkout — pre-count safe."""
    tmp = tempfile.mkdtemp(prefix='deskill-git-')
    try:
        _run(['clone', '-q', '--depth', '1', '--filter=blob:none', '--no-checkout', url, tmp])
        sha = _run(['-C', tmp, 'rev-parse', 'HEAD']).strip()
        yield tmp, sha
    finally:
        _rmtree(tmp)


def ls_tree(repo_dir: str, sha: str) -> list[str]:
    out = _run(['-C', repo_dir, 'ls-tree', '-r', '--name-only', sha])
    return [line for line in out.splitlines() if line]


def checkout_subtree(repo_dir: str, sha: str, sub: str, dest: Path) -> None:
    """Populate only `sub` (sparse) at `sha` and copy it to dest (replacing it)."""
    if sub:
        _run(['-C', repo_dir, 'sparse-checkout', 'set', sub])
    _run(['-C', repo_dir, 'checkout', '-q', sha])
    src = Path(repo_dir) / sub if sub else Path(repo_dir)
    if not src.is_dir():
        raise GitError(f'no directory {sub!r} at revision {sha}')
    if dest.exists():
        _rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('.git'))


def fetch_at_rev(url: str, sha: str, sub: str, dest: Path) -> None:
    """Fetch a pinned revision by sha (allowAnySHA1InWant) and copy `sub` to dest."""
    tmp = tempfile.mkdtemp(prefix='deskill-git-')
    try:
        _run(['init', '-q', tmp])
        _run(['-C', tmp, 'remote', 'add', 'origin', url])
        _run(['-C', tmp, 'fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', sha])
        checkout_subtree(tmp, sha, sub, dest)
    finally:
        _rmtree(tmp)
