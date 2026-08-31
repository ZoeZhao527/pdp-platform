#!/usr/bin/env bash
# 回滚脚本：从 deploy/backups/ 选一个备份还原
#
# 用法：
#   本机回滚:
#     bash scripts/rollback.sh --to deploy_20260831_103000
#   远程回滚:
#     bash scripts/rollback.sh --to deploy_20260831_103000 --host user@host --dest ~/pdp-platform
#
# 不带 --to 则回滚到最近一次备份:
#     bash scripts/rollback.sh --local
#     bash scripts/rollback.sh --host user@host --dest ~/pdp-platform

set -euo pipefail

MODE="remote"
REMOTE_HOST=""
REMOTE_DEST=""
TARGET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)  MODE="local"; shift;;
    --host)   REMOTE_HOST="$2"; shift 2;;
    --dest)   REMOTE_DEST="$2"; shift 2;;
    --to)     TARGET="$2"; shift 2;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "未知参数: $1" >&2; exit 2;;
  esac
done

if [[ "$MODE" == "remote" && -z "$REMOTE_HOST" ]]; then
  echo "错误: 远程回滚需要 --host user@host" >&2; exit 2
fi
[[ "$MODE" == "remote" && -z "$REMOTE_DEST" ]] && REMOTE_DEST="~/pdp-platform"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$PROJECT_DIR/deploy"
BACKUP_DIR="$DEPLOY_DIR/backups"
LOG_FILE="$DEPLOY_DIR/deploy.log"
STAMP="$(date +%Y%m%d_%H%M%S)"

log()  { echo "[$(date '+%F %T')] [$STAMP] [ROLLBACK] $*" | tee -a "$LOG_FILE"; }
fail() { log "❌ 回滚失败: $*"; exit 1; }

remote() { ssh "$REMOTE_HOST" "bash -lc '$*'"; }

# ---------- 选定目标备份 ----------
pick_target_local() {
  if [[ -z "$TARGET" ]]; then
    TARGET="$(ls -1dt "$BACKUP_DIR"/deploy_* 2>/dev/null | head -n1 | xargs -r basename)" || true
    [[ -z "$TARGET" ]] && fail "没有可用的备份"
  fi
  [[ ! -d "$BACKUP_DIR/$TARGET" ]] && fail "备份不存在: $TARGET"
  log "回滚目标: $TARGET"
}

pick_target_remote() {
  local base="$(dirname "$REMOTE_DEST")/backups"
  if [[ -z "$TARGET" ]]; then
    TARGET="$(remote "ls -1dt '$base'/deploy_* 2>/dev/null | head -n1 | xargs -r basename")" || true
    [[ -z "$TARGET" ]] && fail "远程没有可用的备份"
  fi
  remote "[[ -d '$base/$TARGET' ]]" || fail "远程备份不存在: $TARGET"
  log "回滚目标: $TARGET"
}

if [[ "$MODE" == "local" ]]; then pick_target_local; else pick_target_remote; fi

# ---------- 警告 ----------
log "⚠️  即将用备份 $TARGET 覆盖当前代码 + 数据库"
log "⚠️  回滚后请人工确认数据完整性"

# ---------- 还原 ----------
restore_local() {
  local src="$BACKUP_DIR/$TARGET"
  [[ -d "$src/app" ]] && rm -rf "$PROJECT_DIR/backend/app.bak" && cp -R "$PROJECT_DIR/backend/app" "$PROJECT_DIR/backend/app.bak" && rm -rf "$PROJECT_DIR/backend/app" && cp -R "$src/app" "$PROJECT_DIR/backend/app"
  [[ -f "$src/pdp.db" ]] && cp "$PROJECT_DIR/backend/pdp.db" "$PROJECT_DIR/backend/pdp.db.bak.$STAMP" && cp "$src/pdp.db" "$PROJECT_DIR/backend/pdp.db"
  [[ -f "$src/.env" ]] && cp "$src/.env" "$PROJECT_DIR/.env"
  log "  本地还原完成（旧代码留 app.bak，旧库留 pdp.db.bak.$STAMP）"
}

restore_remote() {
  local base="$(dirname "$REMOTE_DEST")/backups"
  remote "cd '$REMOTE_DEST' \
    && [[ -d '$base/$TARGET/app' ]] && rm -rf app.bak && cp -R app app.bak && rm -rf app && cp -R '$base/$TARGET/app' app \
    ; [[ -f '$base/$TARGET/pdp.db' ]] && cp pdp.db pdp.db.bak.$STAMP && cp '$base/$TARGET/pdp.db' pdp.db \
    ; [[ -f '$base/$TARGET/.env' ]] && cp '$base/$TARGET/.env' .env"
  log "  远程还原完成"
}

if [[ "$MODE" == "local" ]]; then restore_local; else restore_remote; fi

# ---------- 重启 ----------
log "重启服务..."
if [[ "$MODE" == "local" ]]; then
  launchctl unload "$DEPLOY_DIR/com.pdp.platform.plist" 2>/dev/null || true
  launchctl load "$DEPLOY_DIR/com.pdp.platform.plist"
  sleep 2
  launchctl list | grep -q "com.pdp.platform" || fail "LaunchAgent 未启动"
else
  remote "launchctl unload '~/Library/LaunchAgents/com.pdp.platform.plist' 2>/dev/null || true \
    && launchctl load '~/Library/LaunchAgents/com.pdp.platform.plist' \
    && sleep 2 && launchctl list | grep -q 'com.pdp.platform'" \
    || fail "远程 LaunchAgent 未启动"
fi

# ---------- 健康检查 ----------
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/v1/health}"
if [[ "$MODE" == "remote" ]]; then
  remote "curl -fsS '$HEALTH_URL' >/dev/null" || fail "健康检查失败: $HEALTH_URL"
else
  curl -fsS "$HEALTH_URL" >/dev/null || fail "健康检查失败: $HEALTH_URL"
fi

log "✅ 回滚成功 (from $TARGET)"
log "  如需再次回滚到回滚前状态，备份名: deploy_$(date +%Y%m%d_%H%M%S)_prerollback (app.bak / pdp.db.bak.$STAMP)"
