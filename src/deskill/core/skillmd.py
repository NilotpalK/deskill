"""SKILL.md wire format (PROTOCOL.md §2): optional YAML frontmatter + markdown body."""
from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Skill:
    frontmatter: dict
    body: str


def parse_skill_md(text: str) -> Skill:
    if not text.startswith('---\n') and not text.startswith('---\r\n'):
        return Skill(frontmatter={}, body=text)
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip('\r\n') == '---':
            fm = yaml.safe_load(''.join(lines[1:i]))
            if not isinstance(fm, dict):
                fm = {}
            return Skill(frontmatter=fm, body=''.join(lines[i + 1:]))
    raise ValueError('unclosed frontmatter block (no closing --- fence)')


def require_trigger_fields(fm: dict) -> None:
    """§2: name + description are what becomes resident; refuse loudly without them."""
    for field in ('name', 'description'):
        v = fm.get(field)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f'frontmatter lacks a usable {field!r} — cannot feed the auto-trigger index')
