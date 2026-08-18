"""deskill CLI: get | save | triggers | prompt.

For humans testing, and for non-MCP agents to shell out to (PROTOCOL.md §8.1).
"""
import argparse
import sys
from pathlib import Path

from deskill.core import (
    Options, add_trigger_line, atskills_root, build_autotrigger_index,
    estimate_tokens, expand_local_triggers, is_cloud, normalize_id,
    parse_triggers, remove_trigger_line, resolve, save,
)


def _opts() -> Options:
    return Options(working_dir=Path.cwd())


def _cmd_get(args) -> int:
    r = resolve(args.id, _opts())
    if not r.success:
        print(r.error, file=sys.stderr)
        return 1
    if r.source == 'stale':
        print('warning: source unreachable — serving the cached copy (stale)',
              file=sys.stderr)
    print(r.content)
    return 0


def _cmd_save(args) -> int:
    r = save(args.id, _opts())
    if not r.success:
        print(r.error, file=sys.stderr)
        return 1
    if r.warning:
        print(f'warning: {r.warning}', file=sys.stderr)
    print(f'saved to {r.dest}')
    return 0


def _cmd_triggers(args) -> int:
    root = atskills_root(_opts())
    root.mkdir(exist_ok=True)
    if args.action == 'add':
        line = f'@{args.id}' if is_cloud(normalize_id(args.id)) else args.id
        added = add_trigger_line(root, line)
        print(f'{"added" if added else "already present"}: {line}')
        if added and not any(not e.error and e.line == line
                             for e in expand_local_triggers(root)):
            print(f'note: {line} currently matches nothing', file=sys.stderr)
        return 0
    if args.action == 'remove':
        removed = remove_trigger_line(root, args.id)
        print(f'{"removed" if removed else "not present"}: {args.id}')
        return 0
    for e in parse_triggers(root):  # list
        print(e.line)
    return 0


def _cmd_prompt(args) -> int:
    block = build_autotrigger_index(_opts())
    if block:
        print(block)  # stdout stays spliceable — the count goes to stderr
        print(f'~{estimate_tokens(block)} tokens', file=sys.stderr)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='deskill',
        description='@skills protocol client (SylphAI, arXiv 2608.12610)')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('get', help='resolve a reference; print the skill or menu')
    p.add_argument('id')
    p.set_defaults(fn=_cmd_get)

    p = sub.add_parser('save', help='vendor a copy into .atskills/ (adapt + detach)')
    p.add_argument('id')
    p.set_defaults(fn=_cmd_save)

    p = sub.add_parser('triggers', help='manage .atskills/.autotrigger lines')
    p.add_argument('action', nargs='?', default='list', choices=['add', 'remove', 'list'])
    p.add_argument('id', nargs='?')
    p.set_defaults(fn=_cmd_triggers)

    p = sub.add_parser('prompt', help='print the residency block to splice into a prompt')
    p.set_defaults(fn=_cmd_prompt)

    args = parser.parse_args(argv)
    if getattr(args, 'action', None) in ('add', 'remove') and not args.id:
        parser.error(f'triggers {args.action} needs an id')
    try:
        return args.fn(args)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
