#!/usr/bin/env bash
# Sincroniza la config de infra al VPS y relanza el stack. Corre en tu máquina.
# Lee MN_HOST y MN_REMOTE de backend/.env.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source backend/.env; set +a
: "${MN_HOST:?define MN_HOST en backend/.env}" "${MN_REMOTE:?define MN_REMOTE en backend/.env}"

ssh "$MN_HOST" "mkdir -p $MN_REMOTE/infra $MN_REMOTE/backend"
rsync -az infra/ "$MN_HOST:$MN_REMOTE/infra/"
rsync -az backend/.env "$MN_HOST:$MN_REMOTE/backend/.env"
ssh "$MN_HOST" "cd $MN_REMOTE && docker compose -f infra/docker-compose.prod.yml pull && docker compose -f infra/docker-compose.prod.yml up -d"
