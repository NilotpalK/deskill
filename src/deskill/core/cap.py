"""The collection cap — 128 skills per reference (PROTOCOL.md §8.3).

The cap counts skills, never files; the check runs before bodies are fetched;
a refusal names the shallowest sub-paths that fit.
"""
from dataclasses import dataclass

MAX_COLLECTION_SKILLS = 128


@dataclass(frozen=True)
class Suggestion:
    rel: str
    count: int


class CollectionTooLargeError(Exception):
    def __init__(self, message: str, count: int, suggestions: list[Suggestion]):
        super().__init__(message)
        self.count = count
        self.suggestions = suggestions


def leaf_skill_dirs(paths: list[str]) -> list[str]:
    dirs = set()
    for p in paths:
        if p == 'SKILL.md':
            dirs.add('')
        elif p.endswith('/SKILL.md'):
            d = p[: -len('/SKILL.md')]
            if d != '.git' and not d.startswith('.git/'):
                dirs.add(d)
    kept: list[str] = []
    for d in sorted(dirs):  # ancestors sort before descendants
        if any(k == '' or d == k or d.startswith(k + '/') for k in kept):
            continue  # a SKILL.md inside another skill's bundle is that bundle's file
        kept.append(d)
    return kept


def _tree(skill_rels: list[str]) -> dict:
    root: dict = {}
    for rel in skill_rels:
        node = root
        for seg in rel.split('/'):
            node = node.setdefault(seg, {})
        node['\0skill'] = True  # marker: this node is a skill
    return root


def _count(node: dict) -> int:
    return int(node.get('\0skill', False)) + sum(
        _count(v) for k, v in node.items() if k != '\0skill')


def largest_usable_collections(skill_rels: list[str]) -> list[Suggestion]:
    """Biggest loadable collection first; descends past oversized parents."""
    found: dict[tuple, Suggestion] = {}

    def members(node: dict, prefix: str = '') -> list[str]:
        out = []
        if node.get('\0skill'):
            out.append(prefix)
        for k, v in node.items():
            if k != '\0skill':
                out.extend(members(v, f'{prefix}/{k}' if prefix else k))
        return sorted(out)

    def visit(node: dict, rel: str) -> None:
        for k, v in node.items():
            if k == '\0skill':
                continue
            child_rel = f'{rel}/{k}' if rel else k
            n = _count(v)
            if n <= MAX_COLLECTION_SKILLS:
                # ponytail: dedupe by (basename, member shape) — repeated vendored
                # catalogs collapse to the shortest path; a same-shaped but genuinely
                # different collection colliding is acceptable for a suggestion list
                key = (k, tuple(members(v)))
                cur = found.get(key)
                if cur is None or (len(child_rel), child_rel) < (len(cur.rel), cur.rel):
                    found[key] = Suggestion(rel=child_rel, count=n)
            else:
                visit(v, child_rel)

    visit(_tree(skill_rels), '')
    return sorted(found.values(), key=lambda s: (-s.count, s.rel))


def assert_collection_fits(paths: list[str], id_prefix: str) -> None:
    skills = leaf_skill_dirs(paths)
    if len(skills) <= MAX_COLLECTION_SKILLS:
        return
    all_suggestions = largest_usable_collections(skills)
    real = [s for s in all_suggestions if s.count > 1]
    suggestions = real if real else all_suggestions
    rows = '\n'.join(f'  {id_prefix}/{s.rel}  ({s.count})' for s in suggestions[:20])
    raise CollectionTooLargeError(
        f'{id_prefix} holds {len(skills)} skills — over the {MAX_COLLECTION_SKILLS} '
        f'a single reference may load.\n'
        f'Reference a specific skill, or one of the collections inside it:\n{rows}',
        count=len(skills), suggestions=suggestions)
