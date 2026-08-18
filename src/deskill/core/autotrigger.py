""".autotrigger — install is a line (PROTOCOL.md §7). Gitignore semantics over .atskills/."""
from dataclasses import dataclass, field
from pathlib import Path

from pathspec import GitIgnoreSpec

from .fsx import walk_skills
from .ids import disk_path, normalize_id
from .skillmd import parse_skill_md, require_trigger_fields


@dataclass(frozen=True)
class TriggerEntry:
    line: str
    cloud: bool


@dataclass(frozen=True)
class ExpandedTrigger:
    line: str
    rel: str = ''
    fm: dict = field(default_factory=dict)
    where: str = ''      # 'yours' | 'saved' | 'cloud'
    origin: str = ''
    error: str = ''


def _at_file(root: Path) -> Path:
    return Path(root) / '.autotrigger'


def parse_triggers(root: Path) -> list[TriggerEntry]:
    f = _at_file(root)
    if not f.is_file():
        return []
    out, seen = [], set()
    for raw in f.read_text(encoding='utf-8').splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue  # only whole-line comments; a # inside a pattern is literal
        if line in seen:
            continue  # duplicates load once
        seen.add(line)
        out.append(TriggerEntry(line=line, cloud=line.startswith('@')))
    return out


def has_trigger_line(root: Path, line: str) -> bool:
    return any(e.line == line.strip() for e in parse_triggers(root))


def add_trigger_line(root: Path, line: str) -> bool:
    line = line.strip()
    if has_trigger_line(root, line):
        return False
    f = _at_file(root)
    existing = f.read_text(encoding='utf-8') if f.is_file() else ''
    if existing and not existing.endswith('\n'):
        existing += '\n'
    f.write_text(existing + line + '\n', encoding='utf-8')
    return True


def remove_trigger_line(root: Path, line: str) -> bool:
    line = line.strip()
    f = _at_file(root)
    if not f.is_file():
        return False
    lines = f.read_text(encoding='utf-8').splitlines()
    kept = [ln for ln in lines if ln.rstrip() != line]
    if len(kept) == len(lines):
        return False
    f.write_text('\n'.join(kept) + ('\n' if kept else ''), encoding='utf-8')
    return True


def _is_pattern(line: str) -> bool:
    return line.endswith('/') or any(c in line for c in '*?[')


def _closest_source(root: Path, skill_dir: Path) -> tuple[str, str]:
    """(where, origin): 'saved' + origin id when a .source covers the dir, else 'yours'."""
    d = skill_dir
    root = Path(root)
    while True:
        src = d / '.source'
        if src.is_file():
            origin = src.read_text(encoding='utf-8').strip().split('\n')[0].strip()
            return 'saved', origin
        if d == root:
            return 'yours', ''
        d = d.parent


def _load(root: Path, rel: str, line: str) -> ExpandedTrigger:
    skill_dir = Path(root) / rel
    try:
        fm = parse_skill_md((skill_dir / 'SKILL.md').read_text(encoding='utf-8')).frontmatter
        require_trigger_fields(fm)
    except (OSError, ValueError) as e:
        return ExpandedTrigger(line=line, rel=rel, error=str(e))
    where, origin = _closest_source(root, skill_dir)
    return ExpandedTrigger(line=line, rel=rel, fm=fm, where=where, origin=origin)


def expand_local_triggers(root: Path, opts=None) -> list[ExpandedTrigger]:
    """Frontmatter of every resident skill; per-line failures are entries, never raises."""
    entries = parse_triggers(root)
    if not entries:
        return []
    root = Path(root)
    rels = walk_skills(root)
    plain = [e.line for e in entries if not e.cloud]
    matched = []
    if plain:
        spec = GitIgnoreSpec.from_lines(plain)  # ONE ruleset — negation composes as in git
        matched = [r for r in rels if r and spec.match_file(r)]

    result: list[ExpandedTrigger] = []
    seen: set[str] = set()
    for e in entries:
        if e.cloud:
            try:
                id = normalize_id(e.line[1:])
            except ValueError as ex:
                result.append(ExpandedTrigger(line=e.line, error=str(ex)))
                continue
            rel = disk_path(id)
            if (root / rel).is_dir():  # a saved copy answers its own @ line
                if rel not in seen:
                    seen.add(rel)
                    result.append(_load(root, rel, e.line))
            elif opts is not None:
                from .resolve import resolve  # deferred: resolve imports nothing from here
                r = resolve(id, opts)
                if r.success and r.kind == 'skill':
                    try:
                        fm = parse_skill_md(r.content).frontmatter
                        require_trigger_fields(fm)
                        result.append(ExpandedTrigger(line=e.line, rel=rel, fm=fm,
                                                      where='cloud', origin=id))
                    except ValueError as ex:
                        result.append(ExpandedTrigger(line=e.line, rel=rel, error=str(ex)))
                else:
                    result.append(ExpandedTrigger(line=e.line, rel=rel, error=r.error))
            else:
                result.append(ExpandedTrigger(
                    line=e.line, rel=rel,
                    error=f'{e.line}: not saved locally and offline expansion has no resolver'))
            continue
        if e.line.startswith('!'):
            continue  # negations only carve; they never load
        line_spec = GitIgnoreSpec.from_lines([e.line])
        line_rels = [r for r in matched if line_spec.match_file(r)]
        for r in line_rels:
            if r not in seen:
                seen.add(r)
                result.append(_load(root, r, e.line))
        if not line_rels and not _is_pattern(e.line):
            # exact lines that load nothing are reported; silent globs match git
            result.append(ExpandedTrigger(line=e.line, error=f'{e.line} matches nothing'))
    return result
