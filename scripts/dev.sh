#!/usr/bin/env bash
# Proseferno developer mode (macOS / Linux): API with auto-reload + Vite dev server with hot
# module replacement. Add --demo to use canned AI responses. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v uv >/dev/null 2>&1 || { echo "uv is required. Run scripts/setup.sh first."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Node.js is required. Run scripts/setup.sh first."; exit 1; }

uv sync --project backend --quiet
[ -d frontend/node_modules ] || (cd frontend && npm ci --no-audit --no-fund)

trap 'kill 0' EXIT
uv run --project backend proseferno --reload "$@" &
(cd frontend && npm run dev) &

echo
echo "  API:  http://127.0.0.1:8732/docs"
echo "  App:  http://localhost:5173"
echo
wait
