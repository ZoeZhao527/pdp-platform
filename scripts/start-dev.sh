#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "请先安装后端依赖：cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! curl -s http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
  (cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 >/tmp/pdp-backend.log 2>&1 &)
fi

if ! curl -s http://127.0.0.1:5173/ >/dev/null 2>&1; then
  (cd "$ROOT/web" && npm run dev -- --host 0.0.0.0 >/tmp/pdp-web.log 2>&1 &)
fi

sleep 3
open http://localhost:8000

