"""AgentLTL rules in front of GitHub Copilot CLI tool calls.

The rules, the guard, the hooks' logic and the library are agentltl_coding's; this package is
the Copilot CLI side: the hook I/O, where its instructions live, and the harness description
below. Rules use the canonical tool names (``Bash``, ``Write``, ``Edit``, ``Read``...), so
the library and a project's AGENTLTL.yaml work as in Claude Code; Copilot's own names are
mapped onto them.
"""

import os

from agentltl_coding import Harness, configure


def copilot_home() -> str:
    """Copilot CLI's configuration directory (``COPILOT_HOME``, else ``~/.copilot``)."""
    return os.environ.get("COPILOT_HOME") or os.path.join(os.path.expanduser("~"), ".copilot")


# Copilot CLI's tools and their arguments, under the names rules use.
TOOL_ALIASES = {
    "bash": ("Bash", {}),
    "create": ("Write", {"path": "file_path", "file_text": "content"}),
    "edit": ("Edit", {"path": "file_path", "old_str": "old_string", "new_str": "new_string"}),
    "view": ("Read", {"path": "file_path"}),
    "glob": ("Glob", {}),
    "grep": ("Grep", {}),
    "task": ("Task", {}),
    "web_fetch": ("WebFetch", {}),
}

# Files Copilot CLI reads as instructions, and the ways a call writes them.
MEMORY_FILES = ["copilot-instructions.md", "*.instructions.md", "AGENTS.md", "CLAUDE.md",
                "GEMINI.md"]
MEMORY_FIRST = {
    "id": "memory-first",
    "never": [{"tool": ["Write", "Edit"], "where": {"file_path": MEMORY_FILES}},
              {"tool": "*", "where": {"redirect_to": MEMORY_FILES}},
              {"tool": ["tee", "sponge"], "where": {"*": MEMORY_FILES}}],
    "mode": "warn",
    "why": "AGENTLTL rules are enforced on every call; instructions can be forgotten. If what you "
           "are saving says which tool calls or commands to make, avoid, or make first (never X, "
           "always Y before Z, at most N times, only with these arguments), add it to "
           "AGENTLTL.yaml instead, using the /agentltl-rules skill, and leave it out of the "
           "instructions.",
    "fix": "Write the rule with the /agentltl-rules skill. Keep in the instructions only what no "
           "rule can check (facts, preferences, style). If nothing here can be a rule, repeat "
           "this exact call to save it.",
}
MEMORY_NOTE = ("before you add anything to custom instructions (copilot-instructions.md, "
               "*.instructions.md, AGENTS.md), ask whether it is a rule about tool calls or "
               "commands. If it is, add it to AGENTLTL.yaml with the /agentltl-rules skill "
               "instead: rules there are enforced, instructions can be forgotten.")


def _memory(root, user_only, home):
    from .memory import copilot_sources
    return copilot_sources(root, user_only, home)


COPILOT_CLI = Harness(
    name="copilot-cli",
    agent="Copilot",
    user_dir=os.environ.get("COPILOT_HOME") or "~/.copilot",
    shell_tools={"Bash": "command", "powershell": "command"},
    tool_aliases=TOOL_ALIASES,
    builtins={"memory_first": MEMORY_FIRST},
    project_env="COPILOT_PROJECT_DIR",
    skill="/agentltl-{}",
    memory=_memory,
    memory_note=MEMORY_NOTE,
)
configure(COPILOT_CLI)
