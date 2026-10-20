#!/usr/bin/env bash
# Builds both Lambda packages. Requires: sam, uv.   Usage: scripts/sam_build.sh [region]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export NAVIGATOR_ROOT="$ROOT"
cd "$ROOT/infra"
sam build --region "${1:-us-east-2}"
