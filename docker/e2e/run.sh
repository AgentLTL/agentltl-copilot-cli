#!/usr/bin/env bash
# Runs inside the agentltl-copilot image (see ../e2e.sh): installs the plugin from /src as a
# user would, starts the scripted model, runs one `copilot -p` session in /work with
# AGENTLTL.yaml, and leaves what happened in /out. Copilot runs offline on a custom provider
# (the scripted model): no GitHub account is needed.
set -u
here=/src/docker/e2e
export COPILOT_HOME=/root/.copilot COPILOT_OFFLINE=true COPILOT_ALLOW_ALL=true \
    COPILOT_PROVIDER_BASE_URL=http://127.0.0.1:8999/v1 COPILOT_PROVIDER_API_KEY=x \
    COPILOT_MODEL=gpt-4.1 COPILOT_PROVIDER_WIRE_MODEL=scripted
mkdir -p /work /out && cp -r /src /tmp/plugin && rm -rf /tmp/plugin/.venv
cd /work && git init -q && printf 'hello\n' > README.md && git add README.md && git commit -qm init
cp "$here/AGENTLTL.yaml" /work/
copilot --version > /out/version.txt 2>&1
copilot plugin install /tmp/plugin > /out/install.txt 2>&1
python3 /src/vendor/agentltl-coding/e2e/scripted_model.py "$here/script.json" --log /out &
sleep 1
timeout 600 copilot -p "do the scripted steps" --allow-all-tools > /out/copilot.txt 2>&1
echo "exit $?" >> /out/copilot.txt
plugin="$(dirname "$(dirname "$(find "$COPILOT_HOME/installed-plugins" -name hooks.json -path '*agentltl*' | head -1)")")"
[[ -d "$plugin/bin" ]] || plugin="$(dirname "$(find "$COPILOT_HOME/installed-plugins" -name hooks.json | head -1)")"
"$plugin/bin/agentltl" trace > /out/trace.txt 2>&1
