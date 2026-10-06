"""The status line and its install into Copilot CLI's settings."""

import json

from agentltl_copilot import statusline
from agentltl_copilot.cli import PLUGIN_ROOT


def test_line(tmp_path):
    (tmp_path / ".git").mkdir()
    assert "no rules here" in statusline.line({"cwd": str(tmp_path)}, color=False)
    (tmp_path / "AGENTLTL.yaml").write_text("rules: [{id: a, never: rm}]")
    assert statusline.line({"cwd": str(tmp_path)}, color=False,
                           cache=str(tmp_path / "c.json")).startswith("AgentLTL ● 2 rules")


def test_install_sets_the_command_and_the_feature_flag(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"model": "x", "feature_flags": {"enabled": ["OTHER"]}}))
    ok, _ = statusline.install(PLUGIN_ROOT, settings=str(settings), shim_dir=str(tmp_path))
    data = json.loads(settings.read_text())
    assert ok and data["model"] == "x"
    assert data["statusLine"] == {"type": "command", "command": str(tmp_path / "statusline")}
    assert data["feature_flags"]["enabled"] == ["OTHER", "STATUS_LINE"]
    assert "__AGENTLTL_ROOT__" not in (tmp_path / "statusline").read_text()
    assert statusline.uninstall(settings=str(settings), shim_dir=str(tmp_path))[0]
    assert "statusLine" not in json.loads(settings.read_text())
