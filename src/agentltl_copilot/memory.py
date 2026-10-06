"""
agentltl_copilot/memory.py – where GitHub Copilot CLI's instructions live.

Copilot CLI reads custom instructions from ``.github/copilot-instructions.md``,
``.github/instructions/**/*.instructions.md``, ``AGENTS.md`` (also ``CLAUDE.md`` and
``GEMINI.md``), and the user's ``~/.copilot/copilot-instructions.md`` and
``~/.copilot/instructions/``. :func:`copilot_sources` lists the files that apply; the scanner
is agentltl_coding's (:mod:`agentltl_coding.memory`), re-exported here.
"""

from __future__ import annotations

import os
from typing import List

from agentltl_coding.memory import *  # noqa: F401,F403  (scan, split, decline, ...)
from agentltl_coding.memory import PROJECT, USER, Source, files, nested


def copilot_sources(root: str, user_only: bool, home: str) -> List[Source]:
    """The instruction files that apply in project *root*, then the user's. With *user_only*,
    only the user's."""
    base = os.environ.get("COPILOT_HOME") or os.path.join(home, ".copilot")
    user = [Source(os.path.join(base, "copilot-instructions.md"), "instructions", USER)]
    user += [Source(p, "instructions", USER)
             for p in files(os.path.join(base, "instructions"), "*.instructions.md")]
    if user_only:
        return user
    github = os.path.join(root, ".github")
    out = [Source(os.path.join(github, "copilot-instructions.md"), "instructions", PROJECT)]
    out += [Source(p, "instructions", PROJECT)
            for p in files(os.path.join(github, "instructions"), "*.instructions.md")]
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        out.append(Source(os.path.join(root, name), "agents-md", PROJECT))
    out += [Source(p, "agents-md", PROJECT) for p in nested(root, "AGENTS.md")]
    return out + user
