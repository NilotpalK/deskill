"""The residency block (PROTOCOL.md §7): frontmatter only, one spliceable string."""
from .autotrigger import expand_local_triggers
from .resolve import Options, atskills_root

HEADER = 'Auto-triggered Skills (.atskills/.autotrigger):'


def build_autotrigger_index(opts: Options) -> str:
    """The exact prompt block a host splices in. Empty string when nothing triggers."""
    ok = [e for e in expand_local_triggers(atskills_root(opts), opts) if not e.error]
    if not ok:
        return ''
    rows = '\n'.join(
        f'- {e.fm["name"]}: {e.fm["description"]} (.atskills/{e.rel}/SKILL.md)' for e in ok)
    return f'{HEADER}\n{rows}'


def estimate_tokens(text: str) -> int:
    # ponytail: len//4 heuristic — swap in a real tokenizer only if the bench needs exact counts
    return 0 if not text else max(1, len(text) // 4)
