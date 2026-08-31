#!/bin/bash
set -euo pipefail
TS=$(date +%Y%m%d_%H%M%S)
VER=${1:-manual}
OUT=/data/pdp/backup/pre-upgrade-${VER}-${TS}.sql.gz
docker exec pdp-postgres pg_dump -U pdp_user pdp_prod | gzip > "$OUT"
tar -czf /data/pdp/backup/pre-upgrade-${VER}-${TS}-config.tar.gz \
    /opt/pdp-release/.env /opt/pdp-release/docker-compose.prod.yml /opt/pdp-release/deploy
SIZE=$(stat -c%s "$OUT")
PREV=$(ls -t /data/pdp/backup/pdp_*.sql.gz 2>/dev/null | head -1 | xargs stat -c%s 2>/dev/null || echo 0)
if [ "$PREV" != "0" ] && [ "$SIZE" -lt $(( PREV * 80 / 100 )) ]; then
    echo "备份异常偏小，阻断升级"
    exit 1
fi
echo "备份完成：$OUT ($SIZE bytes)"
