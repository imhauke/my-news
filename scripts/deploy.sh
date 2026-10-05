#!/usr/bin/env bash
# Syncs the working tree to the server and rebuilds the production stack there.
# Reads MN_HOST and MN_REMOTE from backend/.env. The server keeps its own backend/.env with the
# production secrets: it is never uploaded from here.
set -euo pipefail
cd "$(dirname "$0")/.."

env_var() { grep -E "^$1=" backend/.env | head -1 | cut -d= -f2-; }
HOST="${MN_HOST:-$(env_var MN_HOST)}"
REMOTE="${MN_REMOTE:-$(env_var MN_REMOTE)}"
: "${HOST:?set MN_HOST in backend/.env}" "${REMOTE:?set MN_REMOTE in backend/.env}"

echo "→ syncing source to $HOST:$REMOTE"
rsync -az --delete \
  --exclude .git --exclude .github --exclude .claude --exclude .impeccable \
  --exclude node_modules --exclude dist --exclude __pycache__ --exclude .venv \
  --exclude .pytest_cache --exclude .ruff_cache --exclude '*.pdf' --exclude backups \
  --exclude .env --exclude '.env.*' --exclude PRODUCT.md --exclude skills-lock.json \
  ./ "$HOST:$REMOTE/"

echo "→ building and restarting (one image at a time to spare the server's memory)"
ssh "$HOST" "cd $REMOTE && test -f backend/.env || { echo 'missing $REMOTE/backend/.env'; exit 1; }
  C='docker compose -f infra/docker-compose.prod.yml'
  \$C build api && \$C build web && \$C up -d --remove-orphans && docker image prune -f >/dev/null && \$C ps --format '{{.Name}}  {{.Status}}'"
