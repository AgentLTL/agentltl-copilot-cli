# GitHub Copilot CLI with Python, for testing the plugin end to end:
#   docker build -t agentltl-copilot docker/
#   docker run --rm -it -e GH_TOKEN -v "$PWD":/plugin agentltl-copilot
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates jq \
 && rm -rf /var/lib/apt/lists/*
ARG COPILOT_VERSION=latest
RUN npm install -g @github/copilot@${COPILOT_VERSION}
RUN git config --global user.name tester && git config --global user.email tester@example.com \
 && git config --global init.defaultBranch main
WORKDIR /work
CMD ["copilot"]
