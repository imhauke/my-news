#!/usr/bin/env bash
# Daily pg_dump from the VPS to a local file. Schedule it with cron on your machine or another server.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source backend/.env; set +a
out="backups/mynews-$(date +%F).dump"
mkdir -p backups
ssh "$MN_HOST" "cd $MN_REMOTE && docker compose -f infra/docker-compose.prod.yml exec -T db pg_dump -U $POSTGRES_USER -Fc $POSTGRES_DB" > "$out"
echo "Backup saved to $out"
