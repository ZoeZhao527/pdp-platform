#!/bin/bash
# =============================================================================
# 消费者运营中台 - CVM 部署主脚本
# 在 CVM 上 /opt/pdp-release/ 目录执行
# 完成阶段二~六：env / compose / nginx / 启动 / 迁移 / 验证 / 备份
# =============================================================================
set -euo pipefail

PROJ=/opt/pdp-release
cd "$PROJ"

# ---------------------------------------------------------------------------
# 阶段二：校验 & 生成 .env
# ---------------------------------------------------------------------------
echo "===== [阶段二] 校验代码 & 生成 .env ====="

# 校验关键文件
FAIL=0
[ -f "$PROJ/backend/app/api/__pycache__/platform_orig.cpython-312.pyc" ] || { echo "FAIL: platform_orig.pyc 不存在"; FAIL=1; }
[ -d "$PROJ/web-dist" ] && [ "$(ls -A "$PROJ/web-dist" 2>/dev/null)" ] || { echo "FAIL: web-dist/ 为空"; FAIL=1; }
[ -d "$PROJ/backend/alembic" ] && [ "$(ls -A "$PROJ/backend/alembic/versions" 2>/dev/null)" ] || { echo "FAIL: alembic/versions/ 为空"; FAIL=1; }
[ "$FAIL" -eq 0 ] || { echo "校验失败，中止部署"; exit 1; }
echo "代码校验通过"

# 生成密钥
PG_PASS=$(openssl rand -hex 16)
AUTH_SECRET=$(openssl rand -hex 32)
ADMIN_PASS=$(openssl rand -hex 10)
DATABASE_URL="postgresql+psycopg://pdp_user:${PG_PASS}@postgres:5432/pdp_prod"

mkdir -p /data/pdp/backup
CRED_FILE=/data/pdp/backup/credentials.txt
cat > "$CRED_FILE" <<EOF
# 消费者运营中台 - 生产环境凭据（自动生成）
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S %Z')

PG_PASSWORD=${PG_PASS}
DATABASE_URL=${DATABASE_URL}
PDP_AUTH_SECRET=${AUTH_SECRET}
PDP_ADMIN_USERNAME=admin
PDP_ADMIN_PASSWORD=${ADMIN_PASS}
EOF
chmod 600 "$CRED_FILE"
echo "凭据已写入 $CRED_FILE"

# 生成 .env
cat > "$PROJ/.env" <<EOF
# ===== 运行时 =====
PDP_ENVIRONMENT=production
ENV=production
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
TZ=Asia/Shanghai

# ===== 默认租户 =====
PDP_DEFAULT_TENANT_ID=tenant-default

# ===== 鉴权 =====
PDP_AUTH_SECRET=${AUTH_SECRET}
PDP_ADMIN_USERNAME=admin
PDP_ADMIN_PASSWORD=${ADMIN_PASS}

# ===== CORS =====
PDP_CORS_ORIGINS=["https://numen-ops.7moor.com"]

# ===== LLM =====
PDP_LLM_DEFAULT_MODEL=hunyuan-pro
PDP_LLM_DEFAULT_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1
PDP_LLM_DEFAULT_API_KEY=
PDP_LLM_LITE_MODEL=hunyuan-lite
PDP_LLM_LITE_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1
PDP_LLM_LITE_API_KEY=
PDP_LLM_FALLBACK_MODEL=deepseek-chat
PDP_LLM_FALLBACK_BASE_URL=https://api.deepseek.com/v1
PDP_LLM_FALLBACK_API_KEY=

# ===== 飞书 =====
PDP_FEISHU_ENABLED=true
PDP_FEISHU_MOCK=false
PDP_FEISHU_APP_ID=
PDP_FEISHU_APP_SECRET=
PDP_FEISHU_CHAT_ID=

# ===== 数据库 =====
DATABASE_URL=${DATABASE_URL}
PDP_DATABASE_URL=${DATABASE_URL}

# ===== Redis =====
REDIS_URL=redis://redis:6379/0
PDP_REDIS_URL=redis://redis:6379/0

# ===== Docker Compose 用 =====
PG_PASSWORD=${PG_PASS}
EOF
echo ".env 已生成"

# 修正 alembic.ini
sed -i "s|^sqlalchemy.url = .*|sqlalchemy.url = ${DATABASE_URL}|g" "$PROJ/backend/alembic.ini"
echo "alembic.ini 已更新"

# ---------------------------------------------------------------------------
# 阶段四：Nginx SSL 证书检测
# ---------------------------------------------------------------------------
echo "===== [阶段四] Nginx SSL 证书检测 ====="
SSL_DIR="/etc/nginx/ssl"
SSL_CRT=""
SSL_KEY=""

if [ -d "$SSL_DIR" ]; then
    # 尝试多种命名
    for f in "$SSL_DIR"/numen-ops.7moor.com_bundle.crt "$SSL_DIR"/numen-ops.7moor.com.crt "$SSL_DIR"/fullchain.pem "$SSL_DIR"/fullchain.crt "$SSL_DIR"/*.crt "$SSL_DIR"/*.pem; do
        [ -f "$f" ] && [ -z "$SSL_CRT" ] && SSL_CRT=$(basename "$f")
    done
    for f in "$SSL_DIR"/numen-ops.7moor.com.key "$SSL_DIR"/privkey.pem "$SSL_DIR"/numen-ops.7moor.com.key "$SSL_DIR"/*.key; do
        [ -f "$f" ] && [ -z "$SSL_KEY" ] && SSL_KEY=$(basename "$f")
    done
fi

if [ -n "$SSL_CRT" ] && [ -n "$SSL_KEY" ]; then
    echo "SSL 证书: $SSL_CRT / $SSL_KEY"
    sed -i "s|__SSL_CRT__|${SSL_CRT}|g" "$PROJ/deploy/nginx/conf.d/pdp.conf"
    sed -i "s|__SSL_KEY__|${SSL_KEY}|g" "$PROJ/deploy/nginx/conf.d/pdp.conf"
    echo "Nginx 配置已写入证书路径"
else
    echo "WARNING: 未在 $SSL_DIR 找到 SSL 证书，Nginx 配置保留占位符，需手动修改"
fi

# ---------------------------------------------------------------------------
# 阶段五：启动 + 迁移 + 验证
# ---------------------------------------------------------------------------
echo "===== [阶段五] 启动中间件 ====="
docker compose -f docker-compose.prod.yml up -d postgres redis

echo "等待 PostgreSQL healthy..."
for i in $(seq 1 12); do
    if docker compose -f docker-compose.prod.yml ps postgres | grep -q "healthy"; then
        echo "PostgreSQL 已就绪"
        break
    fi
    sleep 10
done

echo "===== 执行 Alembic 迁移 ====="
docker compose -f docker-compose.prod.yml run --rm -w /app backend bash -c "
    sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = ${DATABASE_URL}|g' alembic.ini &&
    alembic upgrade head
"
echo "迁移完成"

echo "===== 构建后端镜像 ====="
docker compose -f docker-compose.prod.yml build backend

echo "===== 启动全栈 ====="
docker compose -f docker-compose.prod.yml up -d backend nginx

echo "等待后端 healthy..."
for i in $(seq 1 8); do
    if docker compose -f docker-compose.prod.yml ps backend | grep -q "healthy"; then
        echo "后端已就绪"
        break
    fi
    sleep 10
done

# ---------------------------------------------------------------------------
# 验证清单
# ---------------------------------------------------------------------------
echo ""
echo "===== 验证清单 ====="

echo -n "[1] docker compose ps: "
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null

echo -n "[2] health (内部): "
curl -s http://127.0.0.1:8000/api/v1/health 2>/dev/null || echo "FAIL"

echo -n "[3] HTTP 301: "
curl -sI http://127.0.0.1 2>/dev/null | head -1 || echo "FAIL"

echo -n "[4] HTTPS health: "
curl -sk https://127.0.0.1/api/v1/health 2>/dev/null || echo "FAIL"

echo -n "[5] PG extensions: "
docker exec pdp-postgres psql -U pdp_user -d pdp_prod -c "\dx" 2>/dev/null | grep -E "vector|pgcrypto" || echo "FAIL"

echo "[6] 后端日志最后 30 行（筛掉 DEBUG）:"
docker logs --tail 30 pdp-backend 2>&1 | grep -v DEBUG || echo "(无非DEBUG日志)"

# ---------------------------------------------------------------------------
# 阶段六：备份 & 监控
# ---------------------------------------------------------------------------
echo "===== [阶段六] 备份 & 监控 ====="

chmod +x "$PROJ/scripts/pre-upgrade-backup.sh"

cat > /etc/cron.d/pdp-backup <<'EOF'
0 2 * * * root mkdir -p /data/pdp/backup && docker exec pdp-postgres pg_dump -U pdp_user pdp_prod | gzip > /data/pdp/backup/pdp_$(date +\%Y\%m\%d_\%H\%M).sql.gz
0 4 * * * root find /data/pdp/backup -name "pdp_*.sql.gz" -mtime +30 -delete
EOF
echo "定时备份 cron 已配置"

echo ""
echo "===== 部署完成 ====="
echo ""
echo "自动生成的凭据（仅此一次显示）:"
echo "  DB 密码:       ${PG_PASS}"
echo "  Admin 用户名:   admin"
echo "  Admin 密码:    ${ADMIN_PASS}"
echo "  AUTH_SECRET:   ${AUTH_SECRET}"
echo "  完整凭据文件:   $CRED_FILE"
echo ""
echo "访问地址: https://numen-ops.7moor.com"
echo ""
echo "还需手动完成:"
echo "  1. 填写 LLM Key（.env 里的 PDP_LLM_*_API_KEY）"
echo "  2. 在系统前端「飞书配置」页填写飞书 App ID / Secret / Chat ID"
echo "  3. 在飞书开放平台 → 事件订阅 → 请求地址填:"
echo "     https://numen-ops.7moor.com/webhook/feishu"
echo "     订阅事件: im.message.receive_v1"
echo "     如启用加密，把 Verification Token / Encrypt Key 填到系统飞书配置页"
echo "  4. 飞书权限管理确认已开通:"
echo "     im:message / im:message:send_as_bot / contact:user.base:readonly"
