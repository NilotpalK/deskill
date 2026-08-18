# deskill

**deskill** implements the [@skills protocol](https://github.com/SylphAI-Inc/atskills) (SylphAI, ["@skills: Attention Is All You Have"](https://arxiv.org/abs/2608.12610)) — a clean-room second implementation, written in Python from [PROTOCOL.md](https://github.com/SylphAI-Inc/atskills/blob/main/PROTOCOL.md), delivered as an MCP server and CLI so any MCP-compatible agent (Claude Code, Cursor, Codex, …) becomes a conforming @skills client.

The protocol's thesis: installing a skill bundles three separable functions — content, persistence, auto-triggering — and only the last needs space in your system prompt. *Install less, use more.*

```
@skills:gh:owner/repo/path      read a skill at point of use — zero resident tokens
:save                           vendor a copy into .atskills/ — yours, git-tracked
:install                        one line in .atskills/.autotrigger — frontmatter goes resident
```

## Install

```sh
pip install deskill
```

Requires Python ≥ 3.11 and `git` on PATH (the transport is git itself: shallow, blob-filtered, sparse clones — no API quota, private repos ride your git credentials).

## CLI

```sh
deskill get gh:anthropics/skills/skills/pdf     # print a skill (or a menu for a collection)
deskill get https://github.com/anthropics/skills/tree/main/skills/pdf   # pasted URLs work
deskill save gh:anthropics/skills/skills/pdf    # vendor into .atskills/gh/... with a .source stamp
deskill triggers add my-skill                   # add an .autotrigger line
deskill triggers                                # list lines
deskill prompt                                  # the residency block, ready to splice
```

## MCP setup (Claude Code)

```sh
claude mcp add deskill -- deskill-mcp
```

Or any MCP client, via JSON config:

```json
{ "mcpServers": { "deskill": { "command": "deskill-mcp" } } }
```

Tools: `deskill_get`, `deskill_menu`, `deskill_save`, `deskill_install`, `deskill_uninstall`, `deskill_prompt`.

## Auto-trigger wiring (read this once)

The protocol's install tier puts each installed skill's frontmatter (~50–100 tokens) **resident in the agent's system prompt** so it can fire unprompted. MCP servers cannot write into a host's system prompt, so deskill is deliberately *faithful-but-manual* here: it renders the spec-exact residency block; you splice it in once.

```sh
deskill prompt >> CLAUDE.md      # or paste into your agent's system prompt
```

To keep it fresh automatically in Claude Code, add a SessionStart hook to `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{ "type": "command", "command": "deskill prompt" }]
    }]
  }
}
```

The hook's stdout is injected as session context — the resident block the paper describes, at the freshness the spec asks for (cloud lines revalidate through the cache once per session).

## Conformance

- Behaviors mirror the reference implementation's test suite (IDs and URL normalization, decode-then-validate segment grammar, the leaf rule, the 128-skill collection cap with descending suggestions, local-first resolution through a validating cache, bare-paths-never-fetch, save/`.source`/conflict rules, `.autotrigger` gitignore semantics, the byte-exact residency block). Tests run hermetically against `file://` git remotes.
- Live smoke test: resolves `gh:anthropics/skills/skills/pdf` from real GitHub.

```sh
pip install -e .[dev]
python -m pytest tests/ -q
```

## Out of scope (v1)

`hub:` resolution (the hub API ships later upstream — deskill answers with a pointer to `gh:`), the interactive `/skills` checkbox TUI, auth for private repos beyond what your git credentials already provide, and any server-side trigger matching (it would deviate from the spec).

## License

MIT
