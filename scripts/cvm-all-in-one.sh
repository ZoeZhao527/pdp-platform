#!/bin/bash
# 消费者运营中台 - CVM 一键部署脚本
# 用法: sudo nohup bash /opt/pdp-release/scripts/cvm-all-in-one.sh &
set -eo pipefail

LOG=/tmp/pdp-deploy.log
exec > >(tee -a "$LOG") 2>&1
echo "===== 部署开始 $(date) ====="

# ---- 阶段一：环境初始化 ----
echo "===== [阶段一] 环境初始化 ====="
timedatectl set-timezone Asia/Shanghai
timedatectl set-ntp true 2>/dev/null || echo "NTP skip"

cat > /etc/sysctl.d/99-pdp.conf <<'EOF'
vm.max_map_count=262144
net.core.somaxconn=65535
vm.swappiness=10
fs.file-max=1048576
EOF
sysctl --system > /dev/null 2>&1
echo "内核参数已设置"

mkdir -p /data/pdp/{pgdata,redisdata,logs,backup}
echo "数据目录已创建"

# Docker 安装
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | bash
    echo "Docker 安装完成"
else
    echo "Docker 已安装: $(docker --version)"
fi

mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
    "registry-mirrors": ["https://mirror.ccs.tencentyun.com"],
    "log-driver": "json-file",
    "log-opts": {"max-size": "100m", "max-file": "5"}
}
EOF
systemctl enable --now docker
usermod -aG docker ubuntu 2>/dev/null || true
echo "Docker 配置完成: $(docker --version)"

# ---- 阶段二：校验 & 生成 .env ----
PROJ=/opt/pdp-release
cd "$PROJ"
echo "===== [阶段二] 校验代码 & 生成 .env ====="

FAIL=0
[ -f "$PROJ/backend/app/api/__pycache__/platform_orig.cpython-312.pyc" ] || { echo "FAIL: platform_orig.pyc"; FAIL=1; }
[ -d "$PROJ/web-dist" ] && [ "$(ls -A "$PROJ/web-dist" 2>/dev/null)" ] || { echo "FAIL: web-dist"; FAIL=1; }
[ -d "$PROJ/backend/alembic/versions" ] && [ "$(ls -A "$PROJ/backend/alembic/versions" 2>/dev/null)" ] || { echo "FAIL: alembic"; FAIL=1; }
[ "$FAIL" -eq 0 ] || { echo "校验失败，中止"; exit 1; }
echo "代码校验通过"

rm -f "$PROJ/backend/.env.local"

PG_PASS=$(openssl rand -hex 16)
AUTH_SECRET=$(openssl rand -hex 32)
ADMIN_PASS=$(openssl rand -hex 10)
DATABASE_URL="postgresql+psycopg://pdp_user:${PG_PASS}@postgres:5432/pdp_prod"

CRED_FILE=/data/pdp/backup/credentials.txt
cat > "$CRED_FILE" <<EOF
# 凭据 $(date '+%Y-%m-%d %H:%M:%S')
PG_PASSWORD=${PG_PASS}
DATABASE_URL=${DATABASE_URL}
PDP_AUTH_SECRET=${AUTH_SECRET}
PDP_ADMIN_USERNAME=admin
PDP_ADMIN_PASSWORD=${ADMIN_PASS}
EOF
chmod 600 "$CRED_FILE"

cat > "$PROJ/.env" <<EOF
PDP_ENVIRONMENT=production
ENV=production
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
TZ=Asia/Shanghai
PDP_DEFAULT_TENANT_ID=tenant-default
PDP_AUTH_SECRET=${AUTH_SECRET}
PDP_ADMIN_USERNAME=admin
PDP_ADMIN_PASSWORD=${ADMIN_PASS}
PDP_CORS_ORIGINS=["https://numen-ops.7moor.com"]
PDP_LLM_DEFAULT_MODEL=hunyuan-pro
PDP_LLM_DEFAULT_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1
PDP_LLM_DEFAULT_API_KEY=
PDP_LLM_LITE_MODEL=hunyuan-lite
PDP_LLM_LITE_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1
PDP_LLM_LITE_API_KEY=
PDP_LLM_FALLBACK_MODEL=deepseek-chat
PDP_LLM_FALLBACK_BASE_URL=https://api.deepseek.com/v1
PDP_LLM_FALLBACK_API_KEY=
PDP_FEISHU_ENABLED=true
PDP_FEISHU_MOCK=false
PDP_FEISHU_APP_ID=
PDP_FEISHU_APP_SECRET=
PDP_FEISHU_CHAT_ID=
DATABASE_URL=${DATABASE_URL}
PDP_DATABASE_URL=${DATABASE_URL}
REDIS_URL=redis://redis:6379/0
PDP_REDIS_URL=redis://redis:6379/0
PG_PASSWORD=${PG_PASS}
EOF
echo ".env 已生成"

sed -i "s|^sqlalchemy.url = .*|sqlalchemy.url = ${DATABASE_URL}|g" "$PROJ/backend/alembic.ini"

# ---- 阶段四：Nginx SSL ----
echo "===== [阶段四] Nginx SSL ====="
SSL_DIR="/etc/nginx/ssl"
SSL_CRT=""
SSL_KEY=""
if [ -d "$SSL_DIR" ]; then
    for f in "$SSL_DIR"/*.crt "$SSL_DIR"/*.pem; do
        [ -f "$f" ] && [ -z "$SSL_CRT" ] && SSL_CRT=$(basename "$f")
    done
    for f in "$SSL_DIR"/*.key; do
        [ -f "$f" ] && [ -z "$SSL_KEY" ] && SSL_KEY=$(basename "$f")
    done
fi
if [ -n "$SSL_CRT" ] && [ -n "$SSL_KEY" ]; then
    echo "SSL: $SSL_CRT / $SSL_KEY"
    sed -i "s|__SSL_CRT__|${SSL_CRT}|g" "$PROJ/deploy/nginx/conf.d/pdp.conf"
    sed -i "s|__SSL_KEY__|${SSL_KEY}|g" "$PROJ/deploy/nginx/conf.d/pdp.conf"
else
    echo "WARNING: 未找到 SSL 证书"
fi

# ---- 阶段五：启动 + 迁移 ----
echo "===== [阶段五] 启动 ====="
cd "$PROJ"
docker compose -f docker-compose.prod.yml up -d postgres redis

echo "等待 PostgreSQL..."
for i in $(seq 1 12); do
    docker compose -f docker-compose.prod.yml ps postgres 2>/dev/null | grep -q "healthy" && { echo "PG ready"; break; }
    sleep 10
done

echo "===== Alembic 迁移 ====="
docker compose -f docker-compose.prod.yml run --rm -w /app backend bash -c "
    sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = ${DATABASE_URL}|g' alembic.ini &&
    alembic upgrade head
" 2>&1
echo "迁移完成"

echo "===== 构建后端镜像 ====="
docker compose -f docker-compose.prod.yml build backend 2>&1
echo "构建完成"

echo "===== 启动全栈 ====="
docker compose -f docker-compose.prod.yml up -d backend nginx

echo "等待后端..."
for i in $(seq 1 8); do
    docker compose -f docker-compose.prod.yml ps backend 2>/dev/null | grep -q "healthy" && { echo "backend ready"; break; }
    sleep 10
done

# ---- 验证 ----
echo ""
echo "===== 验证 ====="
echo "[1] containers:"
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null
echo -n "[2] health: "
curl -s http://127.0.0.1:8000/api/v1/health 2>/dev/null || echo "FAIL"
echo -n "[3] PG ext: "
docker exec pdp-postgres psql -U pdp_user -d pdp_prod -c "\dx" 2>/dev/null | grep -E "vector|pgcrypto" || echo "FAIL"
echo "[4] logs:"
docker logs --tail 20 pdp-backend 2>&1 | grep -v DEBUG || echo "(clean)"

# ---- 备份 ----
echo "===== [阶段六] 备份 ====="
chmod +x "$PROJ/scripts/pre-upgrade-backup.sh"
cat > /etc/cron.d/pdp-backup <<'EOF'
0 2 * * * root mkdir -p /data/pdp/backup && docker exec pdp-postgres pg_dump -U pdp_user pdp_prod | gzip > /data/pdp/backup/pdp_$(date +\%Y\%m\%d_\%H\%M).sql.gz
0 4 * * * root find /data/pdp/backup -name "pdp_*.sql.gz" -mtime +30 -delete
EOF
echo "备份 cron 已配置"

echo ""
echo "===== 部署完成 $(date) ====="
echo "凭据:"
echo "  DB: ${PG_PASS}"
echo "  Admin: admin / ${ADMIN_PASS}"
echo "  AUTH: ${AUTH_SECRET}"
echo "  文件: $CRED_FILE"
echo "地址: https://numen-ops.7moor.com"
echo ""
echo "===== ALL_DONE ====="
