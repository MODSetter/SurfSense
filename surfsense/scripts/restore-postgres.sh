#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /absolute/or/relative/path/to/surfsense-db-*.sql.gz" >&2
  exit 1
fi

BACKUP_FILE="$1"
[[ -f "$BACKUP_FILE" ]] || { echo "Backup file not found: $BACKUP_FILE" >&2; exit 1; }

set -a
source ./.env
set +a

DB_USER="${DB_USER:-surfsense}"
DB_NAME="${DB_NAME:-surfsense}"

echo "[WARNING] This will overwrite database '$DB_NAME' in running stack."
read -r -p "Type RESTORE to continue: " CONFIRM
[[ "$CONFIRM" == "RESTORE" ]] || { echo "Aborted."; exit 0; }

echo "Recreating public schema..."
docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "Restoring from $BACKUP_FILE ..."
gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"

echo "Restore complete."
