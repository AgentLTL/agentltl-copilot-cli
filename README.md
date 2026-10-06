# AgentLTL for GitHub Copilot CLI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Copilot CLI plugin](https://img.shields.io/badge/Copilot%20CLI-plugin-000000.svg)](https://docs.github.com/copilot/concepts/agents/copilot-cli/about-cli-plugins)
[![arXiv](https://img.shields.io/badge/arXiv-2607.02599-b31b1b.svg)](https://arxiv.org/abs/2607.02599)
[![Docs](https://img.shields.io/badge/docs-agentltl.github.io-3f51b5.svg)](https://agentltl.github.io/harnesses/copilot-cli/)

> Rules Copilot can't forget.

Custom instructions are advice: Copilot can lose them in a long session or inside a subagent.
AgentLTL checks every tool call against the rules in `AGENTLTL.yaml` **before it runs**, and
refuses the ones that break them.

```
> ship 1.6.0 to prod

  ✗ bash  helm upgrade web repo/web --version 1.6.0 -n prod
    Rule 'promote-what-staging-ran' blocked this call. Nothing was executed.
    Problem: for chart='repo/web', v='1.6.0': no earlier helm_upgrade call had
             namespace='staging', chart='repo/web', version='1.6.0'.

  ✓ bash  helm upgrade web repo/web --version 1.6.0 -n staging
  ✓ bash  curl -fsS https://staging.example.com/health
  ✓ bash  helm upgrade web repo/web --version 1.6.0 -n prod
```

One rule did that:

```yaml
- id: promote-what-staging-ran
  before:
    first: {tool: helm_upgrade, with: {chart: $chart, version: $v, namespace: staging}}
    then:  {tool: helm_upgrade, with: {chart: $chart, version: $v, namespace: prod}}
  scope: project       # the staging deploy may have been yesterday, in another session
```

This is the [Claude Code plugin](https://github.com/AgentLTL/agentltl-claude-code)'s guard,
on Copilot CLI's hooks: the same rule language, the same library, and the same
`AGENTLTL.yaml`, so a project can share one rule file between both agents.

## Features

- **Order-aware rules:** tests before push, plan before apply, staging before prod; per session
  or across the whole project.
- **Variables across calls:** `$variables` tie calls together by their arguments.
- **Real shell parsing:** `git commit -am x && git push -f` is checked as `git_commit` then
  `git_push{force: true}`, all or nothing.
- **Plain-language rules:** ask Copilot to "add a rule: never push to main" (`/agentltl-rules`);
  it writes the rule and tests it before saving.
- **Opt-in rule library:** tested rules for git, secrets, installs and infrastructure
  (`/agentltl-setup`).
- **`finally` rules:** "run the tests before you finish": Copilot is sent back before it ends
  its turn.
- **Secret leak alerts:** when a command's output contains what looks like a credential,
  Copilot is told not to repeat it and to tell you, so you can rotate it.
- **Rules instead of instructions:** when Copilot would write a rule into
  `copilot-instructions.md` or `AGENTS.md`, it writes an enforced rule instead;
  `/agentltl-import` does the same for what your instructions already hold.
- **Fail-safe:** never approves a call; internal errors become a permission prompt.

## Installation

Requires Python 3.10+, git, and GitHub Copilot CLI.

```bash
copilot plugin marketplace add AgentLTL/agentltl-copilot-cli
copilot plugin install agentltl@agentltl
```

The plugin builds its Python environment on first use (in `~/.copilot/plugin-data/`) and does
nothing until there is an `AGENTLTL.yaml`: at a project's root for that project, or in
`~/.copilot/` for every project. Start with `/agentltl-setup` in a Copilot session to pick
rules from the library.

**The `agentltl` command** (validate, check, library, use...) is in the plugin's `bin/`.
`agentltl install-cli` links it into `~/.local/bin`:

```bash
~/.copilot/installed-plugins/agentltl/agentltl/bin/agentltl install-cli
```

**Status line** (experimental in Copilot CLI): `agentltl statusline --install` shows the rules
in force, `AgentLTL ● 4 rules · 2 block · 1 ask · 1 warn`. It sets `statusLine` in
`~/.copilot/settings.json` and switches on the `STATUS_LINE` feature flag.

**Updating:** `copilot plugin update agentltl`.

## Usage

### Rules

```yaml
# AGENTLTL.yaml
use: [tests-before-push, no-force-push, protect-env-files, no-copilot-coauthor]

rules:
  - id: tests-before-push-here
    before: {first: {tool: make, with: {argv: check}}, then: git_push, since: [Edit, Write]}
    why: CI is slow; run the checks locally first.
    mode: warn
  - id: changelog
    finally: {tool: Edit, where: {file_path: CHANGELOG.md}}
    why: Every change gets a CHANGELOG line.
```

Rules name tools as the library does, with Claude Code's names, so one file serves both
agents; Copilot's tools are mapped onto them:

| Copilot CLI | Rules say |
|---|---|
| `bash {command}` | the commands it runs (`git_push`, `pytest`...) |
| `create {path, file_text}` | `Write {file_path, content}` |
| `edit {path, old_str, new_str}` | `Edit {file_path, old_string, new_string}` |
| `view {path}` | `Read {file_path}` |
| `glob`, `grep`, `task`, `web_fetch` | `Glob`, `Grep`, `Task`, `WebFetch` |

The full language (rule kinds, targets, variables, memory, modes) is in the
[rules reference](https://agentltl.github.io/rules/reference/), and the packaged rules in the
[library](https://agentltl.github.io/rules/library/). Library entries for one agent only
(`no-claude-coauthor`, `subagents-on-sonnet` for Claude Code; `no-copilot-coauthor` for
Copilot) switch nothing on in the other, so a shared file stays valid.

### Modes

| Mode | The call is | Who can let it through |
|---|---|---|
| `block` | denied, with the reason | you |
| `warn` | denied once | Copilot, by repeating the exact same call |
| `ask` | sent to you for approval | you |
| `retry` | denied; after the allowed retries, you are asked | you |
| `stop` | denied, and every call is refused until you reply | you |
| `log` | allowed; Copilot is told it broke the rule | n/a |

### Skills and commands

| In Copilot | What it does |
|---|---|
| `/agentltl-setup` | pick packaged rules to switch on |
| `/agentltl-rules` | add, change or remove a rule in plain words |
| `/agentltl-import` | turn custom instructions into enforced rules |
| `/agentltl-status` | the rules in force and what they blocked |

| Command | What it does |
|---|---|
| `agentltl validate` | compile the rule files and list the rules |
| `agentltl check "git push" "pytest" "git push"` | replay steps through the rules |
| `agentltl translate "git commit -am x && git push"` | the calls a command line stands for |
| `agentltl library`, `use NAME`, `unuse NAME` | the packaged rules |
| `agentltl trace`, `reset` | what the guard recorded in this session and project |
| `agentltl memory scan` | statements in your instructions that could be rules |
| `agentltl statusline --install`, `install-cli` | status line; the command on your PATH |

## How it works

Copilot CLI runs the plugin's hooks around every tool call (`hooks.json`):

| Hook | AgentLTL |
|---|---|
| `sessionStart` | lists the rules in force to Copilot |
| `preToolUse` | decides the call: `deny` or `ask` with the reason, or silence |
| `postToolUse`, `postToolUseFailure` | records the call that ran (and whether it failed), passes on notes, scans the output for credentials |
| `userPromptSubmitted` | you replied: lifts a `stop` |
| `agentStop` | sends Copilot back while a `finally` rule is unmet |

Shell command lines are translated by [cli-to-tools](https://github.com/AgentLTL/cli-to-tools)
into the calls they run; the rules are compiled by
[agentltl-coding](https://github.com/AgentLTL/agentltl-coding) into
[AgentLTL](https://github.com/AgentLTL/AgentLTL) formulas, checked on the calls so far. The
[full reference](docs/REFERENCE.md) maps every feature of the Claude Code plugin onto Copilot
CLI.

## Limitations

- **Copilot CLI only.** Copilot in VS Code and the cloud agent use other hook paths and are
  not covered yet.
- **No note on an allowed call before it runs:** Copilot's `preToolUse` answer has no field for
  it, so a `log` rule's note reaches Copilot with the call's result.
- **No permission mode in the payload:** set `AGENTLTL_AUTO=1` for unattended runs
  (`copilot -p ... --allow-all-tools`) so commands the guard can't analyse follow
  `unparseable.auto`.
- **PowerShell** commands are parsed as shell where they can be; the rest are "commands it
  can't analyse".
- The rest is as in the [Claude Code plugin](https://agentltl.github.io/harnesses/claude-code/):
  a rule sees tool calls, not what a script does inside.

## Development

```bash
git clone --recurse-submodules https://github.com/AgentLTL/agentltl-copilot-cli.git
cd agentltl-copilot-cli
scripts/setup.sh --dev
.venv/bin/pytest -q
```

`docker/` has an image with Copilot CLI for trying the plugin end to end:
`docker build -t agentltl-copilot docker/`, then
`docker run --rm -it -e COPILOT_GITHUB_TOKEN -v "$PWD":/plugin agentltl-copilot` and, inside,
`copilot plugin install /plugin`.

## Documentation

[agentltl.github.io](https://agentltl.github.io/harnesses/copilot-cli/), and
[docs/REFERENCE.md](docs/REFERENCE.md) here.

## License

MIT. See [LICENSE](LICENSE).
