#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <version-tag>"
  echo "Example: $0 0.1.0"
  exit 1
fi

TARGET_VERSION="$1"
[[ -f .env ]] || { echo ".env missing in $ROOT_DIR" >&2; exit 1; }

CURRENT_VERSION="$(grep -E '^SURFSENSE_VERSION=' .env | cut -d= -f2- || true)"
CURRENT_VERSION="${CURRENT_VERSION:-latest}"

echo "Current version: $CURRENT_VERSION"
echo "Target version:  $TARGET_VERSION"

cp .env ".env.pre-update.$(date +%Y%m%d-%H%M%S).bak"

python3 - <<'PY' "$TARGET_VERSION"
import pathlib,sys,re
version=sys.argv[1]
p=pathlib.Path('.env')
text=p.read_text()
if re.search(r'^SURFSENSE_VERSION=.*$', text, flags=re.M):
    text=re.sub(r'^SURFSENSE_VERSION=.*$', f'SURFSENSE_VERSION={version}', text, flags=re.M)
else:
    text += f'\nSURFSENSE_VERSION={version}\n'
p.write_text(text)
PY

echo "Pulling images and recreating services..."
docker compose pull
docker compose up -d

echo "Running health check..."
bash "$ROOT_DIR/scripts/health-check.sh"

echo "Update complete."
echo "If needed rollback: restore SURFSENSE_VERSION=$CURRENT_VERSION in .env and run: docker compose up -d"
