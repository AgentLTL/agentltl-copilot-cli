# AgentLTL for GitHub Copilot CLI: full reference

The plugin is the [Claude Code plugin](https://github.com/AgentLTL/agentltl-claude-code)'s
guard on Copilot CLI's hooks. Both are thin layers over
[agentltl-coding](https://github.com/AgentLTL/agentltl-coding), which holds the rule language,
the library, the guard and what the hooks do; each plugin only translates its agent's
payloads, tool names and files.

## Setup

```bash
copilot plugin marketplace add AgentLTL/agentltl-copilot-cli
copilot plugin install agentltl@agentltl
```

- The first hook builds a Python environment in the plugin's data directory
  (`~/.copilot/plugin-data/agentltl/venv-<pins>`), from the commits pinned in `vendor.lock`.
  It needs Python 3.10+ and git. A plugin update that changes the pins builds a new one;
  environments unused for 14 days are removed.
- Rules apply where an `AGENTLTL.yaml` is: the project's (found from the working directory up
  to the git root) and the user's, `~/.copilot/AGENTLTL.yaml` (`$COPILOT_HOME` if set). Without
  either, the hooks exit at once.
- `bin/agentltl` is the command line. Copilot CLI does not put a plugin's `bin/` on the PATH:
  `agentltl install-cli` links it into `~/.local/bin`, and the skills find it in the plugin
  folder otherwise.

## Claude Code plugin features, in Copilot CLI

| Claude Code plugin | Copilot CLI plugin |
|---|---|
| `.claude-plugin/plugin.json`, `marketplace.json` | `plugin.json` at the root, `.github/plugin/marketplace.json` |
| `claude plugin install agentltl@agentltl` | `copilot plugin install agentltl@agentltl` |
| Hooks: `SessionStart`, `PreToolUse`, `UserPromptSubmit`, `PostToolUse`, `PostToolUseFailure`, `Stop` | `sessionStart`, `preToolUse`, `userPromptSubmitted`, `postToolUse`, `postToolUseFailure`, `agentStop` (`hooks.json`, version 1) |
| `${CLAUDE_PLUGIN_ROOT}` in hook commands | the plugin root variable when Copilot sets one, else the install path `~/.copilot/installed-plugins/agentltl/agentltl` |
| `${CLAUDE_PLUGIN_DATA}` | `PLUGIN_DATA`, else `~/.copilot/plugin-data/agentltl` |
| PreToolUse `permissionDecision` deny / ask, with a reason | the same fields, at the top level of the answer |
| PreToolUse `additionalContext` (a note on a call that goes ahead) | no such field: the note is kept and given with the call's result, in `postToolUse` |
| `systemMessage` when a `stop` rule fires | no such field: the deny reason says the session is stopped |
| PostToolUse exit status: `PostToolUseFailure` is status 1 | `postToolUseFailure`, or `toolResult.resultType` other than `success`, is status 1 |
| Stop `decision: block` for `finally` rules | `agentStop` `decision: block` (Copilot allows 8 in a row; `finish_retries` defaults to 2) |
| `permission_mode` (auto modes) | not in the payload: `AGENTLTL_AUTO=1` marks an unattended run |
| `CLAUDE_PROJECT_DIR` | the git root of the working directory |
| Tools `Bash`, `Write`, `Edit`, `Read`, `Glob`, `Grep`, `Task`, `WebFetch` | `bash`, `create`, `edit`, `view`, `glob`, `grep`, `task`, `web_fetch`, mapped onto those names and their arguments, so rules and the library are the same |
| `~/.claude/AGENTLTL.yaml` | `~/.copilot/AGENTLTL.yaml` |
| Memory: `CLAUDE.md`, `.claude/rules/`, auto memory | Custom instructions: `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md`, `AGENTS.md` (also `CLAUDE.md`, `GEMINI.md`), `~/.copilot/copilot-instructions.md`, `~/.copilot/instructions/` |
| Built-in rule `memory-first` | the same, on Copilot's instruction files |
| Skills `/agentltl:setup`, `:rules`, `:import`, `:status` | `/agentltl-setup`, `/agentltl-rules`, `/agentltl-import`, `/agentltl-status` |
| `agentltl` on Claude's PATH | `agentltl install-cli` |
| Status line (`~/.claude/settings.json`) | `statusLine` in `~/.copilot/settings.json` plus the `STATUS_LINE` feature flag (experimental in Copilot CLI) |
| Library `no-claude-coauthor`, `subagents-on-sonnet` | `no-copilot-coauthor`; the Claude Code entries switch nothing on here |

## Hooks

| Event | Input used | Answer |
|---|---|---|
| `sessionStart` | `cwd` | `additionalContext`: the rules in force, one line each (`settings.announce`), or the problems of a broken rule file |
| `preToolUse` | `sessionId`, `cwd`, `toolName`, `toolArgs` (an object, or a JSON string) | `permissionDecision` `deny` or `ask` and `permissionDecisionReason`; nothing when there is no objection |
| `postToolUse` | `toolResult.resultType`, `toolResult.textResultForLlm` | `additionalContext`: a note the rules left on the call, a credential warning |
| `postToolUseFailure` | `error` | the same |
| `userPromptSubmitted` | | lifts a `stop`; `finally` rules may send Copilot back again |
| `agentStop` | | `decision: block` with what a `finally` rule still needs |

The guard never answers `allow`: silence leaves the call to Copilot's own permissions. An
internal error in `preToolUse` answers `ask`, and a non-zero exit would deny the call, so a
broken guard is never silently open. Copilot lets a hook that times out through.

## Modes

| Mode | In Copilot CLI |
|---|---|
| `block` | denied with the reason |
| `warn` | denied once; Copilot may repeat the exact same call to go ahead |
| `ask` | Copilot asks you to approve the call |
| `retry` | denied; after `retries` attempts, you are asked |
| `stop` | denied, and every call is denied until you write again |
| `log` | allowed; Copilot gets the note with the call's result |

## Rules

The rule language is the same in every harness: see the
[rules reference](https://agentltl.github.io/rules/reference/) and the
[library](https://agentltl.github.io/rules/library/). In `agentltl check`, a step may name
Copilot's own tools: `'create {"path": ".env", "file_text": "x"}'`.

## State

Session and project traces live in the plugin's data directory (`sessions/`, `projects/`),
as in the Claude Code plugin: `agentltl trace` shows them, `agentltl reset` forgets them.

## Development

```bash
git clone --recurse-submodules https://github.com/AgentLTL/agentltl-copilot-cli.git
scripts/setup.sh --dev && .venv/bin/pytest -q
```

`tests/fixtures/payloads/` holds payloads captured from Copilot CLI; the tests replay them.
`docker/Dockerfile` is an image with Copilot CLI to try the plugin end to end.
