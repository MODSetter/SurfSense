#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
source ./.env
set +a

DB_USER="${DB_USER:-surfsense}"
DB_NAME="${DB_NAME:-surfsense}"
BACKUP_DIR="${1:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_FILE="$BACKUP_DIR/surfsense-db-$STAMP.sql.gz"

echo "Creating Postgres backup: $OUT_FILE"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip -9 > "$OUT_FILE"

echo "Backup complete: $OUT_FILE"
ls -lh "$OUT_FILE"
