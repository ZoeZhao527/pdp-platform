#!/bin/bash
# =============================================================================
# 消费者运营中台 - 本地 → CVM 一键部署脚本
# 用法: ./scripts/cvm-upload-and-deploy.sh <ssh_target>
# 示例: ./scripts/cvm-upload-and-deploy.sh ubuntu@123.45.67.89
#       ./scripts/cvm-upload-and-deploy.sh root@123.45.67.89
# =============================================================================
set -euo pipefail

SSH_TARGET="${1:?用法: $0 <user@ip>}"
REMOTE_DIR="/opt/pdp-release"

echo "===== [1/4] 上传代码到 ${SSH_TARGET}:${REMOTE_DIR} ====="
# 确保本地 web-dist 已就绪
if [ ! -d web-dist ] || [ -z "$(ls -A web-dist 2>/dev/null)" ]; then
    echo "web-dist 不存在或为空，从 web/dist 复制..."
    cp -r web/dist web-dist
fi

# rsync 上传（排除不需要的文件）
rsync -avz --progress \
    --exclude '.git' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude '*.db' \
    --exclude '.env' \
    --exclude 'web/node_modules' \
    --exclude 'web/src' \
    --exclude 'web/public' \
    --exclude 'web/package*.json' \
    --exclude 'web/vite.config.ts' \
    --exclude 'web/tsconfig*' \
    --exclude 'web/tailwind.config*' \
    --exclude 'web/postcss.config*' \
    --exclude 'web/index.html' \
    --include 'backend/app/api/__pycache__/platform_orig.cpython-312.pyc' \
    ./ "${SSH_TARGET}:${REMOTE_DIR}/"

echo "上传完成"

# 校验关键文件
echo "===== [2/4] 远程校验 ====="
ssh "$SSH_TARGET" "
    FAIL=0
    [ -f ${REMOTE_DIR}/backend/app/api/__pycache__/platform_orig.cpython-312.pyc ] || { echo 'FAIL: platform_orig.pyc'; FAIL=1; }
    [ -d ${REMOTE_DIR}/web-dist ] && [ \"\$(ls -A ${REMOTE_DIR}/web-dist 2>/dev/null)\" ] || { echo 'FAIL: web-dist'; FAIL=1; }
    [ -d ${REMOTE_DIR}/backend/alembic/versions ] && [ \"\$(ls -A ${REMOTE_DIR}/backend/alembic/versions 2>/dev/null)\" ] || { echo 'FAIL: alembic versions'; FAIL=1; }
    if [ \$FAIL -eq 1 ]; then echo '校验失败，中止'; exit 1; fi
    echo '远程校验通过'
"

echo "===== [3/4] 阶段一: CVM 环境初始化 ====="
ssh "$SSH_TARGET" "sudo bash ${REMOTE_DIR}/scripts/cvm-setup.sh"

echo "===== [4/4] 阶段二~六: 部署 ====="
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && sudo bash scripts/cvm-deploy.sh"

echo ""
echo "===== 全部完成 ====="
