#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[ERROR] .env not found at $ROOT_DIR/.env" >&2
  exit 1
fi

set -a
source ./.env
set +a

FRONTEND_PORT="${FRONTEND_PORT:-3929}"
BACKEND_PORT="${BACKEND_PORT:-8929}"
ZERO_CACHE_PORT="${ZERO_CACHE_PORT:-5929}"
SEARXNG_PORT="${SEARXNG_PORT:-}"

command -v docker >/dev/null 2>&1 || { echo "[ERROR] docker not installed" >&2; exit 1; }

echo "\n=== Docker Compose Services ==="
docker compose ps

check_url() {
  local name="$1" url="$2"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 6 "$url" || true)
  if [[ "$code" == "200" ]]; then
    echo "[OK]   $name -> $url (HTTP $code)"
  else
    echo "[FAIL] $name -> $url (HTTP ${code:-000})"
    return 1
  fi
}

echo "\n=== HTTP Health ==="
fail=0
check_url "frontend" "http://127.0.0.1:${FRONTEND_PORT}" || fail=1
check_url "backend" "http://127.0.0.1:${BACKEND_PORT}/health" || fail=1
check_url "zero-cache" "http://127.0.0.1:${ZERO_CACHE_PORT}/keepalive" || fail=1

if [[ -n "$SEARXNG_PORT" ]]; then
  check_url "searxng" "http://127.0.0.1:${SEARXNG_PORT}/healthz" || fail=1
else
  echo "[SKIP] searxng HTTP probe (SEARXNG_PORT not set; service is internal by default)"
fi

echo "\n=== Container Health Status ==="
for cid in $(docker compose ps -q); do
  name="$(docker inspect --format '{{.Name}}' "$cid" | sed 's#^/##')"
  state="$(docker inspect --format '{{.State.Status}}' "$cid")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$cid")"
  echo "- $name: state=$state, health=$health"
done

if [[ $fail -eq 0 ]]; then
  echo "\nAll checks passed."
else
  echo "\nOne or more checks failed." >&2
  exit 2
fi
