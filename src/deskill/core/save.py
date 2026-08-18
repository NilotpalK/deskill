"""Save = adapt + detach (PROTOCOL.md §6): vendor a copy at the ID's own path.

Two-line .source stamp, no update lifecycle. Re-save replaces an unedited copy
(verified by re-fetching at the recorded revision and comparing bytes) and
refuses an edited one. A cap refusal is a verdict: nothing lands.
"""
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .cap import CollectionTooLargeError, assert_collection_fits
from .fsx import safe_join
from .gitx import GitError, _rmtree, checkout_subtree, fetch_at_rev, git_available, \
    ls_tree, probe_head, remote_url, shallow_clone
from .ids import disk_path, gh_parts, is_gh, normalize_id
from .resolve import Options, atskills_root


@dataclass(frozen=True)
class SaveResult:
    success: bool
    dest: Path | None = None
    error: str = ''
    warning: str = ''


_CONFLICT_WAYS_OUT = ('keep yours - delete-and-resave - agent merge with the '
                      'recorded revision as base')


def _read_source(path: Path) -> tuple[str, str]:
    """(origin_id, rev) from a two-line .source stamp."""
    lines = path.read_text(encoding='utf-8').strip().split('\n')
    origin = lines[0].strip()
    rev = lines[1].split('rev:', 1)[1].strip() if len(lines) > 1 and 'rev:' in lines[1] else ''
    return origin, rev


def _files_of(dir: Path) -> dict[str, Path]:
    return {p.relative_to(dir).as_posix(): p
            for p in dir.rglob('*') if p.is_file() and p.name != '.source'}


def _dir_equal(a: Path, b: Path) -> bool:
    fa, fb = _files_of(a), _files_of(b)
    if fa.keys() != fb.keys():
        return False
    return all(fa[k].read_bytes() == fb[k].read_bytes() for k in fa)


def _unedited(saved_dir: Path, origin: str, rev: str, opts: Options) -> bool:
    """Byte-compare a saved copy against upstream at its recorded revision."""
    if not is_gh(origin) or not rev:
        return False  # unverifiable counts as edited (§6)
    p = gh_parts(origin)
    url = remote_url(opts.github_base_url, p.owner, p.repo)
    tmp = Path(tempfile.mkdtemp(prefix='deskill-pin-'))
    try:
        fetch_at_rev(url, rev, p.sub, tmp / 'pin')
        return _dir_equal(saved_dir, tmp / 'pin')
    except GitError:
        return False
    finally:
        _rmtree(tmp)


def save(raw_id: str, opts: Options) -> SaveResult:
    try:
        id = normalize_id(raw_id)
    except ValueError as e:
        return SaveResult(success=False, error=str(e))

    if not id.startswith(('gh:', 'hub:')):
        return SaveResult(success=False, error=(
            f'{id} is a bare path — already the project\'s own local skill; '
            f'nothing to save'))
    if id.startswith('hub:'):
        return SaveResult(success=False, error=(
            'hub: save is not implemented yet (the hub API ships later); '
            'use gh:owner/repo/path'))
    if not git_available():
        return SaveResult(success=False, error='git is required and was not found on PATH')

    p = gh_parts(id)
    url = remote_url(opts.github_base_url, p.owner, p.repo)
    if probe_head(url) is None:
        return SaveResult(success=False, error=f'{url} is unreachable — cannot save {id}')

    root = atskills_root(opts)
    dest = safe_join(root, disk_path(id))

    try:
        with shallow_clone(url) as (tmp, sha):
            paths = ls_tree(tmp, sha)
            if p.sub:
                prefix = p.sub + '/'
                subtree = [q[len(prefix):] for q in paths if q.startswith(prefix)]
                if not subtree:
                    return SaveResult(success=False,
                                      error=f'no directory {p.sub!r} in {p.owner}/{p.repo} at HEAD')
            else:
                subtree = paths
            assert_collection_fits(subtree, id)  # the refusal is a verdict — nothing lands

            warning = ''
            if dest.is_dir():
                own_source = dest / '.source'
                child_sources = [s for s in dest.rglob('.source') if s != own_source]
                if own_source.is_file():
                    origin, rev = _read_source(own_source)
                    if not _unedited(dest, origin, rev, opts):
                        return SaveResult(success=False, dest=dest, error=(
                            f'conflict: the saved copy at .atskills/{disk_path(id)} was '
                            f'edited (or its recorded revision is unverifiable). '
                            f'Ways out: {_CONFLICT_WAYS_OUT}.'))
                elif child_sources:
                    # Parent save widens the copy — absorb only UNEDITED saved children.
                    for src in child_sources:
                        child_dir = src.parent
                        origin, rev = _read_source(src)
                        if not _unedited(child_dir, origin, rev, opts):
                            rel = child_dir.relative_to(dest).as_posix()
                            return SaveResult(success=False, dest=dest, error=(
                                f'parent save refuses: edited saved skill at {rel}. '
                                f'Ways out: {_CONFLICT_WAYS_OUT}.'))
                    warning = ('the collection is a superset of previously saved '
                               'children; their stamps move to one parent .source')
                else:
                    return SaveResult(success=False, dest=dest, error=(
                        f'conflict: .atskills/{disk_path(id)} exists with no .source — '
                        f'the project wrote it. Ways out: {_CONFLICT_WAYS_OUT}.'))

            staging = dest.parent / (dest.name + '.tmp-save')
            checkout_subtree(tmp, sha, p.sub, staging)
            if dest.exists():
                _rmtree(dest)
            staging.rename(dest)
            (dest / '.source').write_text(
                f'{id}\n{date.today().isoformat()} rev:{sha}\n', encoding='utf-8')
            return SaveResult(success=True, dest=dest, warning=warning)
    except CollectionTooLargeError as e:
        return SaveResult(success=False, error=str(e))
    except GitError as e:
        return SaveResult(success=False, error=f'save failed for {id}: {e}')
