# Setting up AgentLTL for GitHub Copilot CLI

These instructions are for GitHub Copilot CLI. A user pasted a prompt asking you to set up this
plugin. Follow the steps in order. Say briefly what you are doing at each step, and stop to ask
the user only where a step says so.

The plugin checks every tool call against the rules in an `AGENTLTL.yaml` file, and refuses
calls that break them. Nothing has to be cloned. The plugin installs from GitHub into
`~/.copilot/installed-plugins/` and works in every project. The only file that lives in a
project is `AGENTLTL.yaml`, at the project root (or in `~/.copilot/` to apply to every project).

## 1. Check the prerequisites

Run `python3 --version` and `git --version`.

- **Python 3.10 or newer and git:** both are needed. If either is missing or Python is
  older, stop and tell the user what to install. On macOS that is `brew install python git`;
  on Debian or Ubuntu, `sudo apt install python3 python3-venv git`.
- **`python3 -m venv`:** run `python3 -m venv --help > /dev/null`. On Debian and Ubuntu it can
  be missing even when Python is installed; the fix is `sudo apt install python3-venv`.

## 2. Look for an earlier setup

Run `copilot plugin list`. If `agentltl` is already listed, skip to step 4.

## 3. Install the plugin

```bash
copilot plugin marketplace add AgentLTL/agentltl-copilot-cli
copilot plugin install agentltl@agentltl
```

If the first command says the marketplace already exists, run
`copilot plugin marketplace update agentltl` instead and continue.

## 4. Prepare the plugin's Python environment

The plugin builds its environment by itself the first time it runs. Building it now means the
first rules can be tested before they go live, so run:

```bash
plugin=~/.copilot/installed-plugins/agentltl/agentltl
"$plugin/scripts/setup.sh"
```

It takes about 10 to 30 seconds and ends with `AgentLTL installed in ...`. From now on, run
the plugin's command line as `"$plugin/bin/agentltl"`. To have a plain `agentltl` on the PATH,
run `"$plugin/bin/agentltl" install-cli` (it links it into `~/.local/bin`).

## 5. Choose the first rules, with the user

The plugin ships a library of tested rules the user can switch on by name. Start there:
read `$plugin/skills/agentltl-setup/SKILL.md` and follow it, writing `"$plugin/bin/agentltl"`
wherever that file says `agentltl`. Run the commands from the project root.

Then ask whether there is anything else Copilot should never do, or always do first, in this
project. For each answer, write a rule following `$plugin/skills/agentltl-rules/SKILL.md`. In
short:

- **Tool names:** rules use the names commands translate to. Check with
  `"$plugin/bin/agentltl" translate "git push --force"`.
- **Explain each rule:** give every rule a `why` (Copilot sees it when blocked) and a `mode`
  matching how strict the user wants it: `block`, `warn`, `ask`, `retry`, `stop` or `log`.
- **Test before saving:** check each rule against commands it should and should not stop:
  `"$plugin/bin/agentltl" check --add draft.yaml "deny: git push --force" "allow: git push"`.
  Fix it until every line ends in `ok` and there is no `WARNING`.

Show the user the final `"$plugin/bin/agentltl" validate` output.

## 6. Finish

Tell the user:

1. **Activate it:** restart Copilot CLI. The plugin is active from then on, in every project
   that has an `AGENTLTL.yaml`.
2. **Try it:** ask Copilot to do something a rule forbids, and watch it get refused with the
   rule's reason.
3. **Browse the library again:** `/agentltl-setup`.
4. **Add or remove rules in plain words:** `/agentltl-rules never touch the lockfile`, or just
   ask Copilot.
5. **See what it is doing:** `/agentltl-status` shows the rules in force and what the guard
   recently blocked.
6. **Updating:** `copilot plugin update agentltl`.

## Troubleshooting

- **`Plugin not found in marketplace`:** run `copilot plugin marketplace update agentltl`, then
  install again.
- **Setup fails with `ensurepip` or `No module named venv`:** install `python3-venv` (step 1).
- **Every call asks for permission with "AgentLTL ... is not installed":** the environment could
  not be built. Run step 4 and read its error.
- **A rule never fires:** run `"$plugin/bin/agentltl" validate` and fix any `WARNING`. It means
  a tool or argument name that no command produces.
