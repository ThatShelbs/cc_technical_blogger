#!/usr/bin/env bash
# Run every check CI runs, in CI order, and print a summary.
#   scripts/check.sh          lint, format check, types, tests, build
#   scripts/check.sh --fix    apply the formatters instead of only checking them
#   scripts/check.sh --e2e    also run the Playwright end-to-end tests
# Keep this list in step with .github/workflows/ci.yml.
set -uo pipefail
cd "$(dirname "$0")/.."

command -v uv >/dev/null 2>&1 || { echo "uv is required. Run scripts/setup.sh first."; exit 1; }

FIX=0
E2E=0
for arg in "$@"; do
  [ "$arg" = "--fix" ] && FIX=1
  [ "$arg" = "--e2e" ] && E2E=1
done

PASSED=0
FAILED=()

step() {
  local label="$1"
  shift
  echo
  echo "  == $label"
  if "$@"; then PASSED=$((PASSED + 1)); else FAILED+=("[$label]"); fi
}

py() { uv run --directory backend "$@"; }
npm_run() { npm --prefix frontend run "$@"; }

if [ "$FIX" = 1 ]; then
  step "Backend lint (fixing)" py ruff check --fix src tests scripts evals
  step "Backend format" py ruff format src tests scripts evals
  step "Frontend format" npm_run format
else
  step "Backend lint" py ruff check src tests scripts evals
  step "Backend format" py ruff format --check src tests scripts evals
  step "Frontend format" npm_run format:check
fi
step "Backend types" py mypy
step "Backend tests" py pytest -q
step "Frontend types are current" py python scripts/export_types.py --check
step "Frontend typecheck" npm_run typecheck
step "Frontend lint" npm_run lint
step "Frontend tests" npm_run test
step "Frontend build" npm_run build
[ "$E2E" = 1 ] && step "End-to-end tests" npm_run e2e

echo
echo "  ----------------------------------------------"
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "  FAILED: ${FAILED[*]}"
  echo "  $PASSED passed. Fix the failures above, or run scripts/check.sh --fix for formatting."
  exit 1
fi
echo "  All $PASSED checks passed."
