#!/usr/bin/env bash
# pg_dump diario del VPS a un fichero local. Programa con cron en tu máquina o en otro servidor.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source backend/.env; set +a
out="backups/mynews-$(date +%F).dump"
mkdir -p backups
ssh "$MN_HOST" "cd $MN_REMOTE && docker compose -f infra/docker-compose.prod.yml exec -T db pg_dump -U $POSTGRES_USER -Fc $POSTGRES_DB" > "$out"
echo "Backup guardado en $out"
