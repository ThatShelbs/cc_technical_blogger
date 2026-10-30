#!/usr/bin/env bash
# Proseferno developer setup (macOS / Linux). Safe to run again at any time.
# Installs what you need to work on the code: uv, Node.js 22+, the Python and web packages,
# and (optionally) the browser used by the end-to-end tests.
# Just want to use the app? Run ./launch.sh in the repository root.
set -euo pipefail
cd "$(dirname "$0")/.."

echo
echo "  Proseferno developer setup"
echo

ask() { read -r -p "  $1 [y/N] " reply && [[ "$reply" =~ ^[Yy] ]]; }

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
  echo "  uv is not installed. It manages Python and the backend environment."
  if ask "Install uv now (curl -LsSf https://astral.sh/uv/install.sh | sh)?"; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  command -v uv >/dev/null 2>&1 || { echo "  Please install uv (https://docs.astral.sh/uv/getting-started/installation/) and run this again."; exit 1; }
fi
echo "  [1/4] uv is ready."

# 2. Node.js 22+
node_major() { node --version 2>/dev/null | sed 's/^v//; s/\..*//' || true; }
if [ "$(node_major)" -lt 22 ] 2>/dev/null || ! command -v node >/dev/null 2>&1; then
  echo "  Node.js 22 or newer is needed to build the web interface."
  if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1 && ask "Install it with brew?"; then
    brew install node
  fi
  if [ "$(node_major)" -lt 22 ] 2>/dev/null || ! command -v node >/dev/null 2>&1; then
    echo "  Please install Node.js 22 LTS (https://nodejs.org) and run this again."
    exit 1
  fi
fi
echo "  [2/4] Node.js $(node_major) is ready."

# 3. Packages
echo "  [3/4] Installing Python and web packages..."
uv sync --project backend --quiet
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci --no-audit --no-fund --loglevel=error)
fi

# 4. Optional: browser for end-to-end tests
if ask "Install the browser for end-to-end tests (about 150 MB)?"; then
  (cd frontend && npx playwright install chromium)
fi

echo
echo "  [4/4] Checking this machine..."
uv run --project backend proseferno doctor || true

cat <<'EOF'
  Next:
    ./launch.sh --demo        try the app with canned responses, no keys needed
    scripts/dev.sh --demo     developer mode with hot reload
    scripts/check.sh          run every check CI runs
    docs/onboarding.md        your first day on the project
EOF
