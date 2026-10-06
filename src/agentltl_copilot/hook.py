"""
agentltl_copilot/hook.py – the GitHub Copilot CLI hook: ``python -m agentltl_copilot.hook
EVENT`` reads the event JSON on stdin and prints the hook's JSON answer.

    sessionStart        remind Copilot of the rules; report a broken rule file
    preToolUse          deny / ask when a call breaks a rule (a `stop` denies every call
                        until the user writes), else stay silent
    postToolUse         add the call that ran to the session and project traces (status 0, or
                        1 when its result is not a success); pass on a note the rules left on
                        the call, and warn when its output contains a credential
    postToolUseFailure  the same for a call that failed (status 1)
    userPromptSubmitted the user wrote: lift a stop; `finally` rules may send Copilot back again
    agentStop           Copilot is about to finish: while a `finally` rule is unmet, send it
                        back with what is missing (at most settings.finish_retries times a turn)

Without an AGENTLTL.yaml (project or ``~/.copilot``) it exits at once. It never approves a
call: silence leaves the decision to Copilot's own permissions. An internal error during
preToolUse turns into "ask", so a broken guard is visible instead of failing open.

Copilot CLI's preToolUse answer has no field for a note to the agent, so a note on a call
that goes ahead (a `log` rule, an unparseable command) is kept and given to Copilot with
the call's result, in postToolUse.

Two things Copilot CLI does that the hooks account for: a shell command that exits non-zero
still reports ``resultType: success``, its exit code only in the text
(``<shellId: 3 completed with exit code 1>``); and the reason of an agentStop block comes
back as a userPromptSubmitted whose prompt is that reason, which is not the user replying.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

from . import COPILOT_CLI  # noqa: F401  (configures the harness)

_NOTES = "copilot_notes"
_SENT_BACK = "copilot_sent_back"          # the reason of the last agentStop block
_EXIT = re.compile(r"<shellId: \S+ completed with exit code (\d+)>\s*$")


def main(argv: Optional[list] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    out = run(argv[0] if argv else "", payload if isinstance(payload, dict) else {})
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


def run(event: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The hook's answer to one event, or None for no output."""
    event = event or payload.get("hook_event_name", "")
    try:
        from agentltl_coding import Session
        from agentltl_coding.cli import _git_root
        cwd = _get(payload, "cwd") or os.getcwd()     # the hook itself runs in the plugin folder
        project = os.environ.get("COPILOT_PROJECT_DIR") or _git_root(cwd) or cwd
        session = Session(cwd, project, _get(payload, "sessionId", "session_id"))
        if not session.files:
            return None
        return _handle(event, payload, session)
    except Exception as exc:  # the guard must not fail open silently
        return _failure(event, exc)


def _handle(event: str, payload: Dict[str, Any], session: Any) -> Optional[Dict[str, Any]]:
    from agentltl_coding.rules import RuleFileError

    if event == "userPromptSubmitted":
        if not _echo_of_block(session, payload.get("prompt")):
            session.prompt()
        return None
    try:
        session.ruleset
    except RuleFileError as exc:
        return _broken_file(event, exc.problems)

    if event == "sessionStart":
        text = session.start()
        return {"additionalContext": text} if text else None
    tool, tool_input = _call(payload)
    if event in ("postToolUse", "postToolUseFailure"):
        failed = event == "postToolUseFailure"
        result = payload.get("toolResult") or payload.get("tool_response") or {}
        if failed:
            output, status = payload.get("error"), 1
        elif isinstance(result, dict):
            output = result.get("textResultForLlm")
            status = 0 if result.get("resultType", "success") == "success" else 1
            m = _EXIT.search(output or "") if isinstance(output, str) else None
            if m:
                status = 0 if m.group(1) == "0" else 1
        else:
            output, status = result, 0
        found = session.post(tool, tool_input, "", output, status=status)
        notes = [n for n in (_take_note(session, tool, tool_input), found and found[1]) if n]
        return {"additionalContext": "\n".join(notes)} if notes else None
    if event == "agentStop":
        verdict = session.finish()
        if verdict.action != "block":
            return None
        _remember_block(session, verdict.reason)
        return {"decision": "block", "reason": verdict.reason}
    if event == "preToolUse":
        verdict = session.pre(tool, tool_input, auto=os.environ.get("AGENTLTL_AUTO") == "1")
        if verdict.action in ("deny", "stop", "ask"):
            reason = "\n".join(t for t in (verdict.reason, verdict.context) if t)
            return {"permissionDecision": "ask" if verdict.action == "ask" else "deny",
                    "permissionDecisionReason": reason}
        if verdict.context:
            _keep_note(session, tool, tool_input, verdict.context)
    return None


def _get(payload: Dict[str, Any], *keys: str) -> Any:
    return next((payload[k] for k in keys if payload.get(k) not in (None, "")), None)


def _call(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """The tool and its arguments: ``toolArgs`` is an object, or a JSON string in some
    Copilot CLI versions."""
    tool = _get(payload, "toolName", "tool_name") or ""
    args = _get(payload, "toolArgs", "tool_input")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"command": args} if tool in ("bash", "powershell") else {}
    return tool, args if isinstance(args, dict) else {}


# ── notes kept from preToolUse for postToolUse ────────────────────────────────

def _key(tool: str, tool_input: Dict[str, Any]) -> str:
    raw = json.dumps([tool, tool_input], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _keep_note(session: Any, tool: str, tool_input: Dict[str, Any], text: str) -> None:
    from agentltl_coding import store
    with store.locked(session.sid) as state:
        notes = state.setdefault(_NOTES, {})
        notes[_key(tool, tool_input)] = text
        while len(notes) > 50:
            notes.pop(next(iter(notes)))


def _take_note(session: Any, tool: str, tool_input: Dict[str, Any]) -> Optional[str]:
    from agentltl_coding import store
    with store.locked(session.sid) as state:
        return (state.get(_NOTES) or {}).pop(_key(tool, tool_input), None)


# ── an agentStop block comes back as a prompt ──────────────────────────────────

def _remember_block(session: Any, reason: str) -> None:
    from agentltl_coding import store
    with store.locked(session.sid) as state:
        state[_SENT_BACK] = reason


def _echo_of_block(session: Any, prompt: Any) -> bool:
    """Whether *prompt* is the reason of our last agentStop block, coming back."""
    from agentltl_coding import store
    with store.locked(session.sid) as state:
        sent = state.pop(_SENT_BACK, None)
    return bool(sent) and isinstance(prompt, str) and prompt.strip() == sent.strip()


# ── trouble ───────────────────────────────────────────────────────────────────

def _broken_file(event: str, problems: list) -> Optional[Dict[str, Any]]:
    from agentltl_coding.session import broken
    text = broken(problems)
    if event == "sessionStart":
        return {"additionalContext": text + "\nTell the user at the start of your first reply."}
    if event in ("postToolUse", "postToolUseFailure"):
        return {"additionalContext": text + "\nTell the user."}
    return None


def _failure(event: str, exc: Exception) -> Optional[Dict[str, Any]]:
    text = f"AgentLTL guard error ({type(exc).__name__}: {exc})"
    if event == "preToolUse":
        return {"permissionDecision": "ask",
                "permissionDecisionReason": text + "; this call was NOT checked against the rules."}
    if event == "sessionStart":
        return {"additionalContext": text + "; NO rules are enforced. Tell the user at the start "
                                            "of your first reply."}
    if event in ("postToolUse", "postToolUseFailure"):
        return {"additionalContext": text + ". Tell the user."}
    return None


if __name__ == "__main__":
    sys.exit(main())
