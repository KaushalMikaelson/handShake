#!/usr/bin/env bash
# Full check: backend test suite + frontend typecheck and build.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> backend tests"
cd "$ROOT/backend"
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt; }
./.venv/bin/python -m pytest ../tests -q

echo
echo "==> frontend typecheck + build"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --silent
npm run build
