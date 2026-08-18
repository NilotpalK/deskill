"""deskill MCP server: six tools over deskill.core, stdio transport.

Auto-trigger is faithful-but-manual: deskill_prompt returns the spec-exact
residency block; the user wires it into their agent's system prompt (README).
"""
from pathlib import Path

from mcp.server import MCPServer

from deskill.core import (
    Options, add_trigger_line, atskills_root, build_autotrigger_index,
    estimate_tokens, is_cloud, normalize_id, parse_skill_md,
    remove_trigger_line, require_trigger_fields, resolve, save,
)

mcp = MCPServer(
    'deskill',
    instructions=('Client for the @skills protocol (SylphAI, arXiv 2608.12610). '
                  'Skills are addressed by path: gh:owner/repo/path for GitHub, '
                  'bare paths for project-local skills under .atskills/.'))


def _opts() -> Options:
    return Options(working_dir=Path.cwd())


def get_impl(id: str) -> str:
    r = resolve(id, _opts())
    if not r.success:
        return r.error
    prefix = 'warning: source unreachable — serving stale cached copy\n\n' \
        if r.source == 'stale' else ''
    return prefix + r.content


def menu_impl(id: str) -> str:
    r = resolve(id, _opts())
    if not r.success:
        return r.error
    if r.kind == 'skill':
        return f'{r.id} is a single skill, not a collection:\n\n{r.content}'
    return r.content


def save_impl(id: str) -> str:
    r = save(id, _opts())
    if not r.success:
        return r.error
    note = f'\nwarning: {r.warning}' if r.warning else ''
    return f'saved to {r.dest}{note}'


def install_impl(id: str) -> str:
    opts = _opts()
    r = resolve(id, opts)
    if not r.success:
        return r.error
    if r.kind == 'skill':
        try:
            require_trigger_fields(parse_skill_md(r.content).frontmatter)
        except ValueError as e:
            return f'refusing to install {r.id}: {e}'
    root = atskills_root(opts)
    root.mkdir(exist_ok=True)
    line = f'@{r.id}' if is_cloud(r.id) else r.id
    added = add_trigger_line(root, line)
    return f'{"added" if added else "already present"}: {line}'


def uninstall_impl(id: str) -> str:
    opts = _opts()
    try:
        norm = normalize_id(id)
    except ValueError as e:
        return str(e)
    root = atskills_root(opts)
    for line in (id.strip(), norm, f'@{norm}'):
        if remove_trigger_line(root, line):
            return f'removed: {line}'
    return f'not present: {id}'


def prompt_impl() -> str:
    block = build_autotrigger_index(_opts())
    if not block:
        return ('No skills auto-trigger (empty or missing .atskills/.autotrigger). '
                'Install one with deskill_install, then wire this tool\'s output '
                'into your agent\'s system prompt / CLAUDE.md — see the README.')
    return f'{block}\n\n(~{estimate_tokens(block)} tokens)'


@mcp.tool(name='deskill_get')
def deskill_get(id: str) -> str:
    """Resolve an @skills reference (gh:owner/repo/path, a pasted GitHub URL, or a project-local path) and return the skill's SKILL.md, or a menu when the path is a collection."""
    return get_impl(id)


@mcp.tool(name='deskill_menu')
def deskill_menu(id: str) -> str:
    """List the skills under a collection path, one line per skill (path: description). Paths holding more than 128 skills are refused with viable sub-paths."""
    return menu_impl(id)


@mcp.tool(name='deskill_save')
def deskill_save(id: str) -> str:
    """Vendor a copy of a cloud skill into the project at .atskills/<path> (adapt + detach, with a two-line .source provenance stamp). Re-save refreshes an unedited copy and refuses an edited one."""
    return save_impl(id)


@mcp.tool(name='deskill_install')
def deskill_install(id: str) -> str:
    """Add one line to .atskills/.autotrigger so the skill's frontmatter goes resident (auto-triggers). Refuses skills lacking name/description frontmatter."""
    return install_impl(id)


@mcp.tool(name='deskill_uninstall')
def deskill_uninstall(id: str) -> str:
    """Remove a skill's line from .atskills/.autotrigger."""
    return uninstall_impl(id)


@mcp.tool(name='deskill_prompt')
def deskill_prompt() -> str:
    """Render the residency block for all auto-triggered skills — the exact text to splice into the agent's system prompt (frontmatter only; bodies load on trigger)."""
    return prompt_impl()


def run() -> None:
    mcp.run('stdio')


if __name__ == '__main__':
    run()
