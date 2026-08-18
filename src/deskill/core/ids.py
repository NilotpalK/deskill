"""@skills ID grammar (PROTOCOL.md §4, §8.2.1): normalize, parse, disk paths.

The path is the identity. Bare and hub: IDs fold case; gh: preserves it.
Percent-decoding happens BEFORE segment validation, per §8.2.1.
"""
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
import re


@dataclass(frozen=True)
class Reference:
    id: str
    whole_dir: bool
    save: bool
    install: bool


@dataclass(frozen=True)
class GhParts:
    owner: str
    repo: str
    sub: str


_CTRL = re.compile(r'[\x00-\x1f\x7f]')
_GITHUB_HOSTS = ('github.com', 'www.github.com')


def _validate_segment(seg: str) -> str:
    seg = unquote(seg)  # decode BEFORE validating (§8.2.1)
    if seg in ('', '.', '..') or '/' in seg or '\\' in seg or _CTRL.search(seg):
        raise ValueError(f'invalid path segment: {seg!r}')
    return seg


def _urlish(s: str) -> bool:
    return ('://' in s.split('/', 1)[0] + ('/' if '/' in s else '')
            or s.split('/', 1)[0].lower() in _GITHUB_HOSTS
            or s.lower().startswith(('http://', 'https://')))


def _github_url_to_id(raw: str) -> str:
    u = urlsplit(raw if '://' in raw else 'https://' + raw)
    if (u.hostname or '').lower() not in _GITHUB_HOSTS:
        raise ValueError(f'not a GitHub URL: {raw}')
    parts = [p for p in u.path.split('/') if p]
    if len(parts) < 2:
        raise ValueError(f'not a repository URL: {raw}')
    owner, repo = parts[0], parts[1].removesuffix('.git')
    rest = parts[2:]
    if rest and rest[0] in ('tree', 'blob'):
        rest = rest[2:]  # drop marker + branch
    if rest and rest[-1] == 'SKILL.md':
        rest = rest[:-1]
    segments = [_validate_segment(s) for s in [owner, repo, *rest]]
    return 'gh:' + '/'.join(segments)


def _split_body(body: str) -> list[str]:
    if body.endswith('/'):
        body = body[:-1]  # one trailing slash is browser-paste tolerance
    return body.split('/')


def normalize_id(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError('empty reference')
    low = raw.lower()
    if low.startswith(('gh:', 'gh/')):
        body = raw[3:]
        if _urlish(body):
            return _github_url_to_id(body)
        segments = [_validate_segment(s) for s in _split_body(body)]
        if len(segments) < 2:
            raise ValueError(f'gh: needs owner/repo at least: {raw}')
        return 'gh:' + '/'.join(segments)  # gh: preserves case
    if low.startswith(('hub:', 'hub/')):
        segments = [_validate_segment(s).casefold() for s in _split_body(raw[4:])]
        if len(segments) != 2:
            raise ValueError(f'hub: is exactly owner/name: {raw}')
        return 'hub:' + '/'.join(segments)
    if _urlish(raw):
        return _github_url_to_id(raw)
    return '/'.join(_validate_segment(s).casefold() for s in _split_body(raw))


def parse_reference(ref: str) -> Reference:
    s = ref.strip().removeprefix('@skills:').removeprefix('@')
    save = install = False
    while True:
        if s.endswith(':save'):
            save, s = True, s[:-5]
        elif s.endswith(':install'):
            install, s = True, s[:-8]
        else:
            break
    whole_dir = s.endswith('/')
    return Reference(id=normalize_id(s), whole_dir=whole_dir, save=save, install=install)


def reference_spelling(id: str) -> str:
    marker = ''
    body = id
    for m in ('gh:', 'hub:'):
        if id.startswith(m):
            marker, body = m, id[len(m):]
            break
    enc = [s.replace('%', '%25').replace(' ', '%20').replace(':', '%3A')
           for s in body.split('/')]
    return marker + '/'.join(enc)


def disk_path(id: str) -> str:
    if id.startswith('gh:'):
        return 'gh/' + id[3:]
    if id.startswith('hub:'):
        return 'hub/' + id[4:]
    return id


def gh_parts(id: str) -> GhParts:
    parts = id[3:].split('/')
    return GhParts(owner=parts[0], repo=parts[1], sub='/'.join(parts[2:]))


def is_gh(id: str) -> bool:
    return id.startswith('gh:')


def is_cloud(id: str) -> bool:
    return id.startswith(('gh:', 'hub:'))


def is_local_only(id: str) -> bool:
    return not is_cloud(id)
