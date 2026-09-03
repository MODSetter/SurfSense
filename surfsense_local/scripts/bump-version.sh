#!/usr/bin/env bash
set -euo pipefail

LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$LOCAL_ROOT/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
  echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "ERROR: '$VERSION' is not valid semver (expected X.Y.Z)" >&2
  exit 1
fi

JSON_FIELD='"version"[[:space:]]*:[[:space:]]*"[^"]*"'
TOML_FIELD='^version[[:space:]]*=[[:space:]]*"[^"]*"'

echo "Bumping surfsense_local to $VERSION"
echo "---------------------------------"

bump() {
  local file="$1" field="$2" replacement="$3"
  if [ ! -f "$file" ]; then
    echo "  SKIP  $file (not found)"
    return
  fi

  local old
  old="$(grep -o "$field" "$file" | head -1 | grep -o '"[^"]*"$' | tr -d '"')"
  if [ -z "$old" ]; then
    echo "ERROR: no version field in $file" >&2
    exit 1
  fi
  if [ "$old" = "$VERSION" ]; then
    echo "  OK    $file ($old -- already up to date)"
    return
  fi

  sed -i "0,/$field/s//$replacement/" "$file"

  if ! grep -qF "$replacement" "$file"; then
    echo "ERROR: failed to rewrite version in $file" >&2
    exit 1
  fi
  echo "  SET   $file ($old -> $VERSION)"
}

bump "$LOCAL_ROOT/backend/pyproject.toml" "$TOML_FIELD" "version = \"$VERSION\""
bump "$LOCAL_ROOT/web/package.json" "$JSON_FIELD" "\"version\": \"$VERSION\""
bump "$LOCAL_ROOT/electron/package.json" "$JSON_FIELD" "\"version\": \"$VERSION\""

echo ""
echo "Syncing lock files..."
if command -v uv &>/dev/null; then
  (cd "$LOCAL_ROOT/backend" && uv lock)
  echo "  OK    surfsense_local/backend/uv.lock"
else
  echo "  SKIP  uv not found -- run 'uv lock' in surfsense_local/backend/ manually"
fi

echo "---------------------------------"
echo "Done. surfsense_local set to $VERSION"
