"""Copilot CLI's custom instructions as the memory `agentltl memory scan` reads."""

import json

from agentltl_copilot import cli, memory


def test_sources_are_copilots_instruction_files(tmp_path):
    root, home = tmp_path / "proj", tmp_path / "home"
    (root / ".github" / "instructions").mkdir(parents=True)
    (root / ".github" / "copilot-instructions.md").write_text("x")
    (root / ".github" / "instructions" / "py.instructions.md").write_text("x")
    (root / "AGENTS.md").write_text("x")
    (root / "sub").mkdir()
    (root / "sub" / "AGENTS.md").write_text("x")
    (home / ".copilot").mkdir(parents=True)
    (home / ".copilot" / "copilot-instructions.md").write_text("x")
    got = [(s.path.replace(str(tmp_path) + "/", ""), s.kind, s.target)
           for s in memory.sources(str(root), home=str(home))]
    assert got == [
        ("proj/.github/copilot-instructions.md", "instructions", "project"),
        ("proj/.github/instructions/py.instructions.md", "instructions", "project"),
        ("proj/AGENTS.md", "agents-md", "project"),
        ("proj/sub/AGENTS.md", "agents-md", "project"),
        ("home/.copilot/copilot-instructions.md", "instructions", "user"),
    ]
    assert [s.target for s in memory.sources(str(root), True, str(home))] == ["user"]


def test_memory_scan_finds_rule_candidates(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / ".github").mkdir()
    (root / ".github" / "copilot-instructions.md").write_text(
        "# Git\n\n- Never run `git push --force` on main.\n- The code is in src/.\n")
    monkeypatch.chdir(root)
    assert cli.main(["memory", "scan", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    [st] = result["statements"]
    assert st["file"] == ".github/copilot-instructions.md"
    assert st["commands"][0]["calls"][0]["name"] == "git_push"


def test_memory_first_warns_on_instruction_files(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / "AGENTLTL.yaml").write_text("rules: []")
    monkeypatch.chdir(root)
    step = 'create {"path": ".github/copilot-instructions.md", "file_text": "x"}'
    assert cli.main(["check", f"deny: {step}", f"allow: {step}",
                     'allow: create {"path": "README.md", "file_text": "x"}']) == 0
