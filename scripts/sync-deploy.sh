#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 先回拉自启实例的运行时数据，避免同步时用开发库覆盖线上新增数据
if [ -f "$HOME/pdp-platform/backend/pdp.db" ]; then
  rsync -a "$HOME/pdp-platform/backend/pdp.db" "$ROOT/backend/pdp.db"
fi

# 同步代码到开机自启目录（保留 .venv 与数据）
rsync -a --delete --exclude .venv --exclude __pycache__ --exclude "*.pyc" \
  "$ROOT/backend/" "$HOME/pdp-platform/backend/"
rsync -a --delete "$ROOT/web/dist/" "$HOME/pdp-platform/web/dist/"

launchctl kickstart -k "gui/$(id -u)/com.pdp.platform" 2>/dev/null || true
echo "已同步并重启自启服务"
