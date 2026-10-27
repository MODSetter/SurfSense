#!/usr/bin/env bash
# Starts an image and checks it: healthy through Caddy, the routes, the guard a
# passwordless instance relies on, and a clean stop. CI runs it before any push.
#   docker/surfsense/smoke.sh <image> [port]
set -euo pipefail

IMAGE="${1:?usage: smoke.sh <image> [port]}"
PORT="${2:-4929}"
NAME="surfsense-smoke"
BASE="http://127.0.0.1:$PORT"

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:80" "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

fail() {
  echo "$1"
  docker logs "$NAME"
  exit 1
}

status=starting
for _ in $(seq 1 60); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$NAME")"
  [ "$status" = healthy ] && break
  [ "$status" = unhealthy ] && break
  sleep 5
done
[ "$status" = healthy ] || fail "not healthy: $status"

expect() { # <code> <description> <curl args...>
  want="$1"
  what="$2"
  shift 2
  got="$(curl -s -o /dev/null -w '%{http_code}' "$@")"
  echo "$what: $got"
  [ "$got" = "$want" ] || fail "$what: expected $want"
}
expect 200 "the API through Caddy" "$BASE/api/health"
expect 200 "the SPA" "$BASE/"
expect 403 "a host other than localhost, without a password" -H 'Host: surfsense.example.com' "$BASE/api/health"
expect 403 "the workers' internal routes" -X POST "$BASE/api/internal/events"
curl -fsS "$BASE/" | grep -q '<title>SurfSense' || fail "the SPA has no SurfSense title"

docker stop -t 30 "$NAME" >/dev/null
code="$(docker inspect -f '{{.State.ExitCode}}' "$NAME")"
echo "stopped with exit code $code"
[ "$code" = 0 ] || fail "stopped with exit code $code"
