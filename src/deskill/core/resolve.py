"""Resolution (PROTOCOL.md §5): local first, by path, through a validating cache."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from .cap import CollectionTooLargeError, assert_collection_fits
from .fsx import safe_join, walk_skills
from .gitx import GitError, git_available, probe_head, remote_url, shallow_clone, ls_tree, checkout_subtree
from .ids import disk_path, gh_parts, is_gh, normalize_id
from .skillmd import parse_skill_md


@dataclass(frozen=True)
class Options:
    working_dir: Path
    cache_dir: Path | None = None
    github_base_url: str = 'https://github.com'


@dataclass(frozen=True)
class Resolved:
    success: bool
    kind: str                      # 'skill' | 'menu' | 'error'
    id: str
    content: str
    path: Path | None = None
    source: str = ''               # 'local' | 'cache' | 'fresh' | 'stale' | ''
    error: str = ''


def atskills_root(opts: Options) -> Path:
    return Path(opts.working_dir) / '.atskills'


def cache_root(opts: Options) -> Path:
    if opts.cache_dir:
        return Path(opts.cache_dir)
    xdg = os.environ.get('XDG_CACHE_HOME')
    return (Path(xdg) if xdg else Path.home() / '.cache') / 'atskills'


def _err(id: str, msg: str) -> Resolved:
    return Resolved(success=False, kind='error', id=id, content=msg, error=msg)


def _description_of(skill_dir: Path) -> str:
    try:
        fm = parse_skill_md((skill_dir / 'SKILL.md').read_text(encoding='utf-8')).frontmatter
        return str(fm.get('description', '')) or '(no description)'
    except (OSError, ValueError):
        return '(unreadable frontmatter)'


def _serve(dir: Path, id: str, source: str) -> Resolved:
    skill_md = dir / 'SKILL.md'
    if skill_md.is_file():
        return Resolved(success=True, kind='skill', id=id,
                        content=skill_md.read_text(encoding='utf-8'),
                        path=dir, source=source)
    rels = walk_skills(dir)
    try:
        assert_collection_fits([f'{r}/SKILL.md' if r else 'SKILL.md' for r in rels], id)
    except CollectionTooLargeError as e:
        return _err(id, str(e))
    rows = '\n'.join(f'{id}/{rel}: {_description_of(dir / rel)}' for rel in rels)
    return Resolved(success=True, kind='menu', id=id, content=rows, path=dir, source=source)


def resolve(raw_id: str, opts: Options) -> Resolved:
    try:
        id = normalize_id(raw_id)
    except ValueError as e:
        return _err(raw_id, str(e))

    # 1. Local first, by path — a saved copy answers its own address (§5.1).
    root = atskills_root(opts)
    local = safe_join(root, disk_path(id))
    if local.is_dir():
        return _serve(local, id, 'local')

    # 2. The prefix decides (§5.0): a bare path never leaves the machine.
    if not id.startswith(('gh:', 'hub:')):
        return _err(id, (
            f'No skill at .atskills/{id}. A bare path is the project\'s own and '
            f'never leaves the machine. For the cloud use gh:owner/repo/path or '
            f'hub:owner/name.'))

    if id.startswith('hub:'):
        # ponytail: hub API ships later upstream — stub until it exists (spec §9)
        return _err(id, (
            f'hub: resolution is not implemented yet (the hub API ships later). '
            f'Use gh:owner/repo/path, or a saved copy at .atskills/{disk_path(id)}.'))

    # 3. gh: through the validating cache (§5.2).
    if not git_available():
        return _err(id, 'git is required to fetch gh: skills and was not found on PATH')
    p = gh_parts(id)
    url = remote_url(opts.github_base_url, p.owner, p.repo)
    content_dir = cache_root(opts) / 'gh' / p.owner / p.repo / p.sub if p.sub \
        else cache_root(opts) / 'gh' / p.owner / p.repo
    rev_file = cache_root(opts) / '.meta' / 'gh' / p.owner / p.repo / (p.sub or '_root') / '.rev'

    head = probe_head(url)
    if head is None:
        if content_dir.is_dir():
            return _serve(content_dir, id, 'stale')
        return _err(id, f'{url} is unreachable and nothing is cached for {id}')

    if content_dir.is_dir() and rev_file.is_file() \
            and rev_file.read_text(encoding='utf-8').strip() == head:
        return _serve(content_dir, id, 'cache')

    try:
        with shallow_clone(url) as (tmp, sha):
            paths = ls_tree(tmp, sha)
            if p.sub:
                prefix = p.sub + '/'
                subtree = [q[len(prefix):] for q in paths if q.startswith(prefix)]
                if not subtree:
                    return _err(id, f'no directory {p.sub!r} in {p.owner}/{p.repo} at HEAD')
            else:
                subtree = paths
            assert_collection_fits(subtree, id)  # BEFORE any blob lands (§8.3)
            checkout_subtree(tmp, sha, p.sub, content_dir)
            rev_file.parent.mkdir(parents=True, exist_ok=True)
            rev_file.write_text(sha, encoding='utf-8')
    except CollectionTooLargeError as e:
        return _err(id, str(e))
    except GitError as e:
        return _err(id, f'fetch failed for {id}: {e}')
    return _serve(content_dir, id, 'fresh')
