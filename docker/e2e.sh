#!/usr/bin/env bash
# End to end, no account needed: GitHub Copilot CLI (the version in package.json) in Docker,
# offline on a custom provider, with the plugin installed from this checkout and
# agentltl-coding's scripted model making the calls in e2e/script.json. Checks that the rules in
# e2e/AGENTLTL.yaml refused what e2e/expected.txt says, and that `finally` sent Copilot back.
#
#   docker/e2e.sh          # E2E_OUT=dir keeps the output there (default: a temporary folder)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker build -q -t agentltl-copilot "$root/docker" > /dev/null
if [[ -n "${E2E_OUT:-}" ]]; then
    mkdir -p "$E2E_OUT" && out="$(cd "$E2E_OUT" && pwd)"
else
    out="$(mktemp -d)"
fi
chmod 777 "$out"
docker run --rm -v "$root":/src:ro -v "$out":/out agentltl-copilot bash /src/docker/e2e/run.sh
echo "$(head -1 "$out/version.txt"), output in $out"
python3 "$root/vendor/agentltl-coding/e2e/check.py" "$out/trace.txt" "$root/docker/e2e/expected.txt"
# The `finally` rule's reason comes back to the model as a new user message.
if grep -l "Before you finish" "$out"/req-*.json > /dev/null 2>&1; then
    echo "OK: Copilot was sent back before finishing."
else
    echo "FAILED: the commit-before-finishing rule did not send Copilot back."
    exit 1
fi
