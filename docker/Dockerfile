# GitHub Copilot CLI with Python, for testing the plugin end to end. The Copilot CLI version
# is pinned in package.json (Dependabot proposes each new release).
#
#   docker/e2e.sh                       # a scripted model, no account needed
#   docker build -t agentltl-copilot docker/
#   docker run --rm -it -e COPILOT_GITHUB_TOKEN -v "$PWD":/plugin agentltl-copilot
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates jq \
 && rm -rf /var/lib/apt/lists/*
COPY package.json /opt/agentltl/package.json
RUN npm install -g "@github/copilot@$(jq -r '.dependencies["@github/copilot"]' /opt/agentltl/package.json)"
RUN git config --global user.name tester && git config --global user.email tester@example.com \
 && git config --global init.defaultBranch main
WORKDIR /work
CMD ["copilot"]
