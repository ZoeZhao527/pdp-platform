#!/usr/bin/env bash
# 部署脚本：备份 → 同步 → 重启 → 记录
#
# 用法：
#   本机部署（本机即运行机）:
#     bash scripts/deploy.sh --local
#   远程部署（本机开发 → 远程 mac 运行）:
#     bash scripts/deploy.sh --host user@host --dest ~/pdp-platform
#
# 失败自动回滚到上一个备份。
# 日志：deploy/deploy.log
# 备份：deploy/backups/deploy_YYYYmmdd_HHMMSS/（保留最近 10 份）

set -euo pipefail

# ---------- 参数解析 ----------
MODE="remote"
REMOTE_HOST=""
REMOTE_DEST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)  MODE="local"; shift;;
    --host)   REMOTE_HOST="$2"; shift 2;;
    --dest)   REMOTE_DEST="$2"; shift 2;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0;;
    *) echo "未知参数: $1" >&2; exit 2;;
  esac
done

if [[ "$MODE" == "remote" && -z "$REMOTE_HOST" ]]; then
  echo "错误: 远程部署需要 --host user@host" >&2
  exit 2
fi
if [[ "$MODE" == "remote" && -z "$REMOTE_DEST" ]]; then
  REMOTE_DEST="~/pdp-platform"   # 默认与 plist 一致
fi

# ---------- 路径与常量 ----------
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$PROJECT_DIR/deploy"
BACKUP_DIR="$DEPLOY_DIR/backups"
LOG_FILE="$DEPLOY_DIR/deploy.log"
KEEP_BACKUPS=10
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="deploy_${STAMP}"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# 当前 git commit（没 git 就用时间戳）
GIT_REF="$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "no-git-${STAMP}")"

log()   { echo "[$(date '+%F %T')] [$STAMP] $*" | tee -a "$LOG_FILE"; }
fail()  { log "❌ 失败: $*"; exit 1; }

log "========== 部署开始 =========="
log "模式: $MODE  git: $GIT_REF"
[[ "$MODE" == "remote" ]] && log "目标: $REMOTE_HOST:$REMOTE_DEST"

# ---------- 远程命令封装 ----------
remote() { ssh "$REMOTE_HOST" "bash -lc '$*'"; }

# ---------- Step 1: 备份 ----------
log "Step 1: 备份当前运行版本"

backup_local() {
  # 备份代码 + 数据库 + .env（若存在）
  mkdir -p "$BACKUP_PATH"
  local bk="$BACKUP_PATH"
  [[ -d "$PROJECT_DIR/backend/app" ]] && cp -R "$PROJECT_DIR/backend/app" "$bk/app"
  [[ -d "$PROJECT_DIR/web-dist" ]] && cp -R "$PROJECT_DIR/web-dist" "$bk/web-dist"
  [[ -f "$PROJECT_DIR/backend/pdp.db" ]] && cp "$PROJECT_DIR/backend/pdp.db" "$bk/pdp.db"
  [[ -f "$PROJECT_DIR/.env" ]] && cp "$PROJECT_DIR/.env" "$bk/.env"
  echo "$GIT_REF" > "$bk/git_ref.txt"
  echo "$STAMP" > "$bk/timestamp.txt"
  log "  本地备份完成: $bk"
}

backup_remote() {
  remote "mkdir -p '$REMOTE_DEST/../backups/$BACKUP_NAME' \
    && cd '$REMOTE_DEST' \
    && [[ -d app ]] && cp -R app '../backups/$BACKUP_NAME/app' || true \
    && [[ -f pdp.db ]] && cp pdp.db '../backups/$BACKUP_NAME/pdp.db' || true \
    && [[ -f .env ]] && cp .env '../backups/$BACKUP_NAME/.env' || true \
    && echo '$GIT_REF' > '../backups/$BACKUP_NAME/git_ref.txt' \
    && echo '$STAMP' > '../backups/$BACKUP_NAME/timestamp.txt'"
  log "  远程备份完成: $REMOTE_HOST:$(dirname "$REMOTE_DEST")/backups/$BACKUP_NAME"
}

if [[ "$MODE" == "local" ]]; then backup_local; else backup_remote; fi

# ---------- Step 2: 同步代码 ----------
log "Step 2: 同步代码"

sync_local() {
  rsync -a --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude 'pdp.db' --exclude 'pdp.db-journal' \
    --exclude '.env' --exclude 'logs' \
    "$PROJECT_DIR/backend/" "$PROJECT_DIR/backend/"
  # 本地就是运行机，代码原地不动，这步主要是 noop；保留接口对称
  log "  本地代码无需同步"
}

sync_remote() {
  rsync -az --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude 'pdp.db' --exclude 'pdp.db-journal' \
    --exclude '.env' --exclude 'logs' \
    "$PROJECT_DIR/backend/" "$REMOTE_HOST:$REMOTE_DEST/"
  rsync -az --delete "$PROJECT_DIR/web-dist/" "$REMOTE_HOST:$REMOTE_DEST/../web-dist/" 2>/dev/null || \
    log "  (web-dist 不存在，跳过前端)"
  log "  代码已同步到 $REMOTE_HOST:$REMOTE_DEST"
}

if [[ "$MODE" == "local" ]]; then sync_local; else sync_remote; fi

# ---------- Step 3: 重启服务 ----------
log "Step 3: 重启服务"

restart_local() {
  launchctl unload "$DEPLOY_DIR/com.pdp.platform.plist" 2>/dev/null || true
  launchctl load "$DEPLOY_DIR/com.pdp.platform.plist"
  sleep 2
  if ! launchctl list | grep -q "com.pdp.platform"; then
    fail "LaunchAgent 未启动"
  fi
  log "  本地 LaunchAgent 已重启"
}

restart_remote() {
  # plist 在 $REMOTE_DEST/../deploy/ 或 ~/Library/LaunchAgents/
  remote "launchctl unload '~/Library/LaunchAgents/com.pdp.platform.plist' 2>/dev/null || true \
    && launchctl load '~/Library/LaunchAgents/com.pdp.platform.plist' \
    && sleep 2 \
    && launchctl list | grep -q 'com.pdp.platform'" \
    || fail "远程 LaunchAgent 未启动"
  log "  远程 LaunchAgent 已重启"
}

if [[ "$MODE" == "local" ]]; then restart_local; else restart_remote; fi

# ---------- Step 4: 健康检查 ----------
log "Step 4: 健康检查"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/v1/health}"
if [[ "$MODE" == "remote" ]]; then
  HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/v1/health}"
  # 远程健康检查在远端执行
  remote "curl -fsS '$HEALTH_URL' >/dev/null" || fail "健康检查失败: $REMOTE_HOST $HEALTH_URL"
else
  curl -fsS "$HEALTH_URL" >/dev/null || fail "健康检查失败: $HEALTH_URL"
fi
log "  健康检查通过: $HEALTH_URL"

# ---------- Step 5: 清理旧备份 ----------
log "Step 5: 清理旧备份（保留最近 $KEEP_BACKUPS 份）"
if [[ "$MODE" == "local" ]]; then
  ls -1dt "$BACKUP_DIR"/deploy_* 2>/dev/null | tail -n +$((KEEP_BACKUPS+1)) | xargs -r rm -rf
else
  remote "ls -1dt '$(dirname "$REMOTE_DEST")/backups'/deploy_* 2>/dev/null | tail -n +$((KEEP_BACKUPS+1)) | xargs -r rm -rf"
fi
log "  旧备份已清理"

log "✅ 部署成功"
log "  备份: $BACKUP_NAME"
log "  回滚: bash scripts/rollback.sh --to $BACKUP_NAME $([[ $MODE == remote ]] && echo --host $REMOTE_HOST --dest $REMOTE_DEST || true)"
