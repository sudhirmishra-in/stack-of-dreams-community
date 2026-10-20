#!/usr/bin/env bash
# Copies the shared `navigator` package into the AgentCore runtime bundle so the deployed zip is
# self-contained. Run before `agentcore deploy`. The copy is git-ignored; src/navigator is the source of truth.
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="agentcore/app/community_navigator/navigator"
rm -rf "$DEST"
mkdir -p "$DEST"
rsync -a --exclude '__pycache__' --exclude '*.pyc' src/navigator/ "$DEST/"
echo "synced $(find "$DEST" -name '*.py' | wc -l | tr -d ' ') python files into $DEST"
