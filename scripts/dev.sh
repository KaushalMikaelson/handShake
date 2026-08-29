#!/usr/bin/env bash
# Run the whole stack locally with no Docker and no credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "==> creating backend venv"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

echo "==> starting API on http://127.0.0.1:8000"
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "==> installing frontend dependencies"
  npm install
fi

echo "==> starting frontend on http://127.0.0.1:5173"
npm run dev
