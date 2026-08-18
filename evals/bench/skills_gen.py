"""Turn domains into a real .atskills project — deskill.core is the instrument."""
import random
from pathlib import Path

from deskill.core import Options, build_autotrigger_index

from .domains import TARGETS, Domain, distractors


def nested_sets(seed: int = 7, sizes=(10, 25, 50, 100)) -> dict[int, list[Domain]]:
    """Nested skill sets: the 10 targets exist at every N; distractors fill the rest."""
    rng = random.Random(seed)
    pool = distractors()
    rng.shuffle(pool)
    out = {}
    for n in sizes:
        out[n] = TARGETS + pool[: n - len(TARGETS)]
    return out


def build_project(working_dir: Path, domains: list[Domain]) -> None:
    for d in domains:
        skill_dir = Path(working_dir) / '.atskills' / d.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / 'SKILL.md').write_text(
            f'---\nname: {d.name}\ndescription: {d.description}\n---\n{d.body}\n',
            encoding='utf-8')


def render_block(working_dir: Path, names: list[str]) -> str:
    """The residency block for `names`, in that order — rendered by deskill itself."""
    at = Path(working_dir) / '.atskills' / '.autotrigger'
    at.write_text('\n'.join(names) + '\n', encoding='utf-8')
    return build_autotrigger_index(Options(working_dir=Path(working_dir)))
