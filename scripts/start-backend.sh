#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /tmp/pdp-backend.log 2>&1

