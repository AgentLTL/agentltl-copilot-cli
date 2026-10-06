"""
agentltl_copilot/cli.py – the ``agentltl`` command of the GitHub Copilot CLI plugin.

Everything agentltl_coding's command does (validate, check, translate, tools, trace, reset,
library, use/unuse, disable/enable, and memory scan/decline/forget over Copilot's custom
instructions), plus what is Copilot CLI's own:

    agentltl statusline [--install]      the status line (reads Copilot CLI's JSON on stdin)
    agentltl install-cli [--dir DIR]     put `agentltl` on your PATH (a link in ~/.local/bin)

``check`` steps may name Copilot's own tools: ``'create {"path": ".env", "file_text": "x"}'``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

from . import COPILOT_CLI  # noqa: F401  (configures the harness)
from agentltl_coding.cli import main as _main

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv: Optional[List[str]] = None) -> int:
    return _main(argv, extend=_extend)


def _extend(sub: Any, commands: Dict[str, Callable[[argparse.Namespace], int]]) -> None:
    p = sub.add_parser("statusline", help="AgentLTL's status line for Copilot CLI")
    p.add_argument("--install", action="store_true",
                   help="show it in Copilot CLI's status line (edits ~/.copilot/settings.json)")
    p.add_argument("--force", action="store_true", help="with --install: replace a status line")
    p.add_argument("--uninstall", action="store_true", help="remove AgentLTL's status line")
    p = sub.add_parser("install-cli", help="put `agentltl` on your PATH")
    p.add_argument("--dir", default=os.path.join("~", ".local", "bin"),
                   help="where to put the link (default: ~/.local/bin)")
    commands["statusline"] = _statusline
    commands["install-cli"] = _install_cli


def _statusline(args: argparse.Namespace) -> int:
    from . import statusline

    if args.install or args.uninstall:
        if args.install:
            ok, message = statusline.install(PLUGIN_ROOT, force=args.force)
        else:
            ok, message = statusline.uninstall()
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    try:
        payload = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
    except ValueError:
        payload = {}
    try:
        print(statusline.line(payload if isinstance(payload, dict) else {}))
    except Exception as exc:          # a status line must print something, never a traceback
        print(f"AgentLTL ⚠ {type(exc).__name__}")
    return 0


def _install_cli(args: argparse.Namespace) -> int:
    """A link to a small script that runs whichever plugin version is installed now (the
    status line's), so plugin updates don't break it."""
    from . import statusline

    folder = os.path.expanduser(args.dir)
    os.makedirs(folder, exist_ok=True)
    shim = os.path.join(statusline.data_dir(), "agentltl")
    with open(os.path.join(PLUGIN_ROOT, "scripts", "statusline"), encoding="utf-8") as fh:
        text = fh.read().replace("__AGENTLTL_ROOT__", PLUGIN_ROOT)
    text = text.replace('exec "$root/bin/agentltl" statusline', 'exec "$root/bin/agentltl" "$@"')
    os.makedirs(os.path.dirname(shim), exist_ok=True)
    with open(shim, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(shim, 0o755)
    link = os.path.join(folder, "agentltl")
    if os.path.lexists(link):
        if os.path.realpath(link) != os.path.realpath(shim):
            print(f"{link} exists and is not AgentLTL's; nothing changed.", file=sys.stderr)
            return 1
        os.remove(link)
    os.symlink(shim, link)
    on_path = folder in os.environ.get("PATH", "").split(os.pathsep)
    print(f"{link} -> {shim}" + ("" if on_path else f"\n{folder} is not on your PATH yet."))
    return 0


__all__ = ["main"]

if __name__ == "__main__":
    sys.exit(main())
