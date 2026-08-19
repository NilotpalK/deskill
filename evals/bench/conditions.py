"""Prompt builders for both delivery conditions, and the LOAD-protocol parser."""
import re

BASE_SYSTEM = (
    'You are a coding assistant embedded in a developer tool. '
    'Answer the user\'s request directly and concisely.')

TRIGGER_INSTRUCTION = (
    'If (and only if) the user\'s task matches one of the Auto-triggered Skills '
    'listed above, respond with exactly one line, LOAD(<path>) — using the path '
    'shown in parentheses for that skill — and nothing else, then wait for the '
    'skill body to be provided. If no listed skill matches, just answer the task.')


def installed_system(block: str) -> str:
    return f'{BASE_SYSTEM}\n\n{block}\n\n{TRIGGER_INSTRUCTION}'


def trigger_user_message(task: str) -> str:
    return task


def padded_system(block: str, padding: str) -> str:
    """Distance-decay condition: the block sits at the top, then `padding` tokens
    of session transcript, so the task lands far from the resident descriptions."""
    return (f'{BASE_SYSTEM}\n\n{block}\n\n{TRIGGER_INSTRUCTION}\n\n'
            f'[Transcript of the session so far]\n{padding}\n[End of transcript]\n\n'
            "The user's next message follows.")


def referenced_messages(body: str, task: str) -> list[dict]:
    """Point-of-use injection: the skill rides at the end of context, next to the task."""
    content = (f'<skill-instructions>\n{body}\n</skill-instructions>\n\n{task}')
    return [{'role': 'user', 'content': content}]


def loaded_continuation(load_line: str, body: str) -> list[dict]:
    """Stage 2 of the installed condition: hand the model the body it asked for."""
    return [
        {'role': 'assistant', 'content': load_line},
        {'role': 'user', 'content': f'Loaded skill body:\n\n{body}\n\nNow complete the original task.'},
    ]


_LOAD = re.compile(r'LOAD\(([^)]+)\)')


def normalize_skill_path(path: str) -> str | None:
    """Canonical .atskills-relative name from however a model spelled the path.

    Models mangle the prefix (./atskills/x, atskills/x, ./.atskills/x) — spelling
    slips, not selection errors, so normalization tolerates them all.
    """
    p = path.strip().strip('`"\'')
    p = p.removeprefix('./')
    p = p.removeprefix('.atskills/').removeprefix('atskills/')
    p = p.removesuffix('/SKILL.md')
    return p.strip('/') or None


def parse_load(reply: str) -> str | None:
    """The skill path the model asked to load, normalized to its .atskills-relative name."""
    m = _LOAD.search(reply)
    if not m:
        return None
    return normalize_skill_path(m.group(1))
