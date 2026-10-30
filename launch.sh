#!/usr/bin/env bash
# Proseferno launcher (macOS / Linux). Extra arguments pass through, e.g. ./launch.sh --demo
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PROSEFERNO_PORT:-8732}"

echo
echo "  Proseferno - technical blogs in your own voice"
echo

# Already running? Just open it.
if curl -fs "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
  echo "  Proseferno is already running on port ${PORT}. Opening it in your browser."
  (command -v open >/dev/null && open "http://127.0.0.1:${PORT}") || (command -v xdg-open >/dev/null && xdg-open "http://127.0.0.1:${PORT}") || true
  exit 0
fi

trap 'echo; echo "  Setup failed. To see what is wrong on this machine, run:"; echo "    uv run --project backend proseferno doctor"' ERR

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  [ "$(uname)" = "Darwin" ] && echo "or:  brew install uv"
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js (LTS) is required: https://nodejs.org"
  [ "$(uname)" = "Darwin" ] && echo "or:  brew install node"
  exit 1
fi

echo "  [1/3] Preparing the Python environment..."
uv sync --project backend --quiet

if [ ! -d frontend/node_modules ]; then
  echo "  [2/3] Installing web interface packages (first run only)..."
  (cd frontend && npm ci --no-audit --no-fund --loglevel=error)
fi
if node frontend/scripts/needs-build.mjs; then
  echo "  [3/3] Building the web interface..."
  (cd frontend && npm run build --silent)
fi

trap - ERR
echo
echo "  Starting Proseferno at http://127.0.0.1:${PORT} (Ctrl+C to stop)"
exec uv run --project backend proseferno --open --port "${PORT}" "$@"
