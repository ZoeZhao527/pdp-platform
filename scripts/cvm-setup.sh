#!/bin/bash
# =============================================================================
# 消费者运营中台 - CVM 环境初始化脚本
# 在 CVM 上执行，完成阶段一（内核/Docker/数据盘）
# =============================================================================
set -euo pipefail

echo "===== [1/5] 时区 & NTP ====="
timedatectl set-timezone Asia/Shanghai
timedatectl set-ntp true 2>/dev/null || echo "NTP skip (not supported)"
echo "时区: $(timedatectl show -p Timezone --value)"

echo "===== [2/5] 内核参数 ====="
cat > /etc/sysctl.d/99-pdp.conf <<'EOF'
vm.max_map_count=262144
net.core.somaxconn=65535
vm.swappiness=10
fs.file-max=1048576
EOF
sysctl --system > /dev/null 2>&1
echo "内核参数已写入 /etc/sysctl.d/99-pdp.conf"

echo "===== [3/5] 数据盘 ====="
if lsblk /dev/vdb > /dev/null 2>&1 && ! mountpoint -q /data; then
    mkfs.ext4 -F /dev/vdb
    echo "/dev/vdb /data ext4 defaults,noatime 0 2" >> /etc/fstab
    mkdir -p /data
    mount /data
    echo "数据盘 /dev/vdb 已挂载到 /data"
else
    mkdir -p /data
    echo "数据盘跳过（不存在或已挂载）"
fi
mkdir -p /data/pdp/{pgdata,redisdata,logs,backup}

echo "===== [4/5] Docker ====="
if ! command -v docker &> /dev/null; then
    curl -fsSL https://mirror.ccs.tencentyun.com/docker/install.sh | bash
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
echo "Docker daemon.json 已配置"

echo "===== [5/5] 校验 ====="
echo "时区: $(timedatectl show -p Timezone --value)"
echo "Docker: $(docker --version)"
echo "Compose: $(docker compose version 2>/dev/null || echo 'NOT FOUND')"
echo "数据盘: $(df -h /data 2>/dev/null || echo 'N/A')"
echo "===== 阶段一完成 ====="
