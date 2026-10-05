#!/usr/bin/env bash
# Syncs the infra config to the VPS and restarts the stack. Runs on your machine.
# Reads MN_HOST and MN_REMOTE from backend/.env.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source backend/.env; set +a
: "${MN_HOST:?set MN_HOST in backend/.env}" "${MN_REMOTE:?set MN_REMOTE in backend/.env}"

ssh "$MN_HOST" "mkdir -p $MN_REMOTE/infra $MN_REMOTE/backend"
rsync -az infra/ "$MN_HOST:$MN_REMOTE/infra/"
rsync -az backend/.env "$MN_HOST:$MN_REMOTE/backend/.env"
ssh "$MN_HOST" "cd $MN_REMOTE && docker compose -f infra/docker-compose.prod.yml pull && docker compose -f infra/docker-compose.prod.yml up -d"
