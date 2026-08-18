"""Filesystem primitives: confined joins and the leaf-rule walk (PROTOCOL.md §1, §8.2.1)."""
import os
from pathlib import Path, PurePosixPath


def safe_join(root: Path, rel: str) -> Path:
    joined = (Path(root) / rel).resolve()
    root = Path(root).resolve()
    if joined != root and not joined.is_relative_to(root):
        raise ValueError(f'path escapes root: {rel!r}')
    return joined


def walk_skills(root: Path) -> list[str]:
    """Rel posix paths of skill dirs under root. Leaf rule: stop at SKILL.md.

    Only .git is excluded — dot-directories ARE skill homes (§8.2.1).
    """
    root = Path(root)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != '.git']
        if 'SKILL.md' in filenames:
            rel = PurePosixPath(Path(dirpath).relative_to(root).as_posix())
            found.append('' if str(rel) == '.' else str(rel))
            dirnames[:] = []  # the walk stops at a skill
    return sorted(found)
