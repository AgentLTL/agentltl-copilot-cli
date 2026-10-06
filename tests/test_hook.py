"""The hook end to end: Copilot CLI event payloads in, hook JSON out."""

import json
import os
import subprocess
import sys

import pytest

from agentltl_copilot import hook
from agentltl_coding import store

RULES = """
rules:
  - id: tests-before-push
    before: {first: pytest, then: git_push, since: [Edit, Write]}
    why: CI is slow.
  - id: no-secrets
    never: [Read, Edit, cat]
    where: {"*": "**/.env"}
    mode: stop
"""


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "AGENTLTL.yaml").write_text(RULES)
    return root


def event(project, name, tool=None, args=None, **extra):
    payload = {"sessionId": "s1", "timestamp": 1, "cwd": str(project), **extra}
    if tool:
        payload.update(toolName=tool, toolArgs=args or {})
    return hook.run(name, payload)


def pre(project, tool, args, **kw):
    return event(project, "preToolUse", tool, args, **kw)


def post(project, tool, args, text="", result="success"):
    return event(project, "postToolUse", tool, args,
                 toolResult={"resultType": result, "textResultForLlm": text})


def bash(command):
    return "bash", {"command": command, "description": "x"}


def test_scenario(project):
    deny = pre(project, *bash("git push"))
    assert deny["permissionDecision"] == "deny"
    assert "tests-before-push" in deny["permissionDecisionReason"]

    post(project, *bash("pytest -q"), "3 passed")
    assert pre(project, *bash("git push")) is None              # silent: no objection

    # an edit that was proposed but never ran does not count; one that ran does
    edit = ("edit", {"path": str(project / "a.py"), "old_str": "a", "new_str": "b"})
    assert pre(project, *edit) is None
    assert pre(project, *bash("git push")) is None
    post(project, *edit)
    assert pre(project, *bash("git push"))["permissionDecision"] == "deny"


def test_tool_args_as_a_json_string(project):
    out = pre(project, "bash", json.dumps({"command": "git push"}))
    assert out["permissionDecision"] == "deny"


def test_stop_denies_everything_until_the_user_writes(project):
    out = pre(project, "view", {"path": str(project / ".env")})
    assert out["permissionDecision"] == "deny" and "stops the session" in out["permissionDecisionReason"]
    held = pre(project, *bash("ls"))
    assert held["permissionDecision"] == "deny" and "stopped this session" in held["permissionDecisionReason"]
    event(project, "userPromptSubmitted", prompt="ok, go on")
    assert pre(project, *bash("ls")) is None


def test_ask_rules_ask(project):
    (project / "AGENTLTL.yaml").write_text("rules: [{id: no-rm, never: rm, mode: ask}]")
    out = pre(project, *bash("rm -rf build"))
    assert out["permissionDecision"] == "ask" and "no-rm" in out["permissionDecisionReason"]


def test_a_note_on_an_allowed_call_comes_with_its_result(project):
    (project / "AGENTLTL.yaml").write_text("rules: [{id: no-sudo, never: sudo, mode: log, why: w}]")
    assert pre(project, *bash("sudo ls")) is None
    out = post(project, *bash("sudo ls"), "x")
    assert "no-sudo" in out["additionalContext"]
    assert post(project, *bash("sudo ls"), "x") is None          # given once


def test_credentials_in_output(project):
    out = post(project, *bash("cat config"), "key=" + "AKIA" + "ABCDEFGHIJKLMNOP")
    assert "AWS access key ID" in out["additionalContext"]


def test_a_failed_command_is_recorded_as_failed(project):
    event(project, "postToolUseFailure", *bash("pytest"), error="exit 1")
    post(project, *bash("ruff check"), "", result="failure")
    post(project, *bash("ls"), "a")
    calls = store.read("s1")["completed_tool_calls"]
    assert [(c["tool_name"], c["status"]) for c in calls] == [("pytest", 1), ("ruff", 1),
                                                              ("ls", 0)]


def test_a_finally_rule_sends_copilot_back_once_per_turn(project):
    (project / "AGENTLTL.yaml").write_text("settings: {finish_retries: 1}\n"
                                           "rules: [{id: tested, finally: pytest}]")
    stop = {"transcriptPath": "/t", "stopReason": "end_turn", "stop_hook_active": False}
    first = event(project, "agentStop", **stop)
    assert first["decision"] == "block" and "tested" in first["reason"]
    assert event(project, "agentStop", **stop) is None
    event(project, "userPromptSubmitted", prompt="again")
    assert event(project, "agentStop", **stop)["decision"] == "block"


def test_session_start_reminds_copilot_of_the_rules(project):
    text = event(project, "sessionStart", source="startup")["additionalContext"]
    assert "tests-before-push" in text and "memory-first" in text and "/agentltl-rules" in text


def test_broken_file_is_loud(project):
    (project / "AGENTLTL.yaml").write_text("rules: [{id: x, nevr: rm}]")
    text = event(project, "sessionStart", source="startup")["additionalContext"]
    assert "NO AGENTLTL rules are being enforced" in text
    assert pre(project, *bash("rm x")) is None


def test_no_rule_file_is_silent(tmp_path):
    (tmp_path / ".git").mkdir()
    assert hook.run("preToolUse", {"cwd": str(tmp_path), "toolName": "bash",
                                   "toolArgs": {"command": "rm -rf /"}}) is None


def test_internal_error_asks_instead_of_failing_open(project, monkeypatch):
    from agentltl_coding import Session
    monkeypatch.setattr(Session, "pre", lambda *a, **k: 1 / 0)
    out = pre(project, *bash("ls"))
    assert out["permissionDecision"] == "ask" and "NOT checked" in out["permissionDecisionReason"]


def test_project_memory_spans_sessions(project):
    (project / "AGENTLTL.yaml").write_text(
        "rules: [{id: tests-ever, before: [pytest, git_push], scope: project}]")
    event(project, "postToolUse", *bash("pytest"), sessionId="a",
          toolResult={"resultType": "success", "textResultForLlm": ""})
    out = hook.run("preToolUse", {"sessionId": "b", "cwd": str(project), "toolName": "bash",
                                  "toolArgs": {"command": "git push"}})
    assert out is None
    assert store.read("b").get("project_dir") == str(project)


def test_launcher(project, tmp_path):
    """hooks/run with the test Python: payload on stdin, JSON on stdout."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, AGENTLTL_COPILOT_PYTHON=sys.executable,
               PYTHONPATH=os.pathsep.join(sys.path))
    payload = json.dumps({"sessionId": "s1", "cwd": str(project), "toolName": "bash",
                          "toolArgs": {"command": "git push"}})
    out = subprocess.run([os.path.join(root, "hooks", "run"), "preToolUse"], input=payload,
                         capture_output=True, text=True, env=env, cwd=str(project), check=True)
    assert json.loads(out.stdout)["permissionDecision"] == "deny"


# ── what Copilot CLI 1.0.92 actually sends (tests/fixtures/payloads) ──────────

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "payloads", "copilot-1.0.92.json")


def test_a_captured_session_replays(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "AGENTLTL.yaml").write_text(
        "use: [no-copilot-coauthor]\n"
        "rules:\n  - {id: tests, before: [pytest, git_commit]}\n"
        "  - {id: no-cat-notes, never: {tool: Read, where: {file_path: '*notes.txt'}}}\n")
    with open(FIXTURE) as fh:
        events = json.load(fh)["events"]
    out = []
    for e in events:
        payload = json.loads(json.dumps(e["payload"]).replace("/work/proj", str(root)))
        answer = hook.run(e["event"], payload)
        if e["event"] == "preToolUse":
            out.append((payload["toolName"], answer and answer["permissionDecision"]))
    assert out == [("bash", None), ("create", None), ("edit", None), ("view", "deny"),
                   ("bash", None), ("skill", None), ("bash", "deny")]
    calls = store.read(events[0]["payload"]["sessionId"])["completed_tool_calls"]
    assert [(c["tool_name"], c.get("status")) for c in calls if c["tool_name"] != "cd"] == [
        ("ls", 0), ("Write", 0), ("Edit", 0), ("Read", 0), ("false", 1), ("skill", 0),
        ("git_add", None), ("git_commit", 0)]      # a command line's status is its last call's


def test_a_shell_exit_code_in_the_text_is_the_status(project):
    post(project, *bash("pytest"), "1 failed\n<shellId: 4 completed with exit code 1>")
    post(project, *bash("ls"), "a\n<shellId: 5 completed with exit code 0>")
    calls = store.read("s1")["completed_tool_calls"]
    assert [(c["tool_name"], c["status"]) for c in calls] == [("pytest", 1), ("ls", 0)]


def test_the_finally_reason_coming_back_as_a_prompt_is_not_the_user(project):
    (project / "AGENTLTL.yaml").write_text("settings: {finish_retries: 1}\n"
                                           "rules: [{id: tested, finally: pytest}]")
    first = event(project, "agentStop", stop_hook_active=False)
    event(project, "userPromptSubmitted", prompt=first["reason"])     # Copilot's echo
    assert event(project, "agentStop", stop_hook_active=True) is None   # retries used up
    event(project, "userPromptSubmitted", prompt="please also fix the docs")
    assert event(project, "agentStop")["decision"] == "block"           # a new turn


def test_the_project_is_copilots_project_dir(project, monkeypatch):
    sub = project / "src"
    sub.mkdir()
    monkeypatch.setenv("COPILOT_PROJECT_DIR", str(project))
    assert pre(project, *bash("git push"), cwd=str(sub))["permissionDecision"] == "deny"
    assert store.read("s1")["project_dir"] == str(project)
