#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$REPO_ROOT/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
  echo "ERROR: VERSION file not found at $VERSION_FILE" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "ERROR: '$VERSION' is not valid semver (expected X.Y.Z)" >&2
  exit 1
fi

echo "Bumping all packages to $VERSION"
echo "---------------------------------"

bump_json() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "  SKIP  $file (not found)"
    return
  fi
  local old
  old="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$file" | head -1)"
  if [ "$old" = "$VERSION" ]; then
    echo "  OK    $file ($old -- already up to date)"
  else
    sed -i "s/\"version\": \"$old\"/\"version\": \"$VERSION\"/" "$file"
    echo "  SET   $file ($old -> $VERSION)"
  fi
}

bump_toml() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "  SKIP  $file (not found)"
    return
  fi
  local old
  old="$(sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$file" | head -1)"
  if [ "$old" = "$VERSION" ]; then
    echo "  OK    $file ($old -- already up to date)"
  else
    sed -i "s/^version = \"$old\"/version = \"$VERSION\"/" "$file"
    echo "  SET   $file ($old -> $VERSION)"
  fi
}

bump_json "$REPO_ROOT/surfsense_web/package.json"
bump_json "$REPO_ROOT/surfsense_browser_extension/package.json"
bump_json "$REPO_ROOT/surfsense_desktop/package.json"
bump_toml "$REPO_ROOT/surfsense_backend/pyproject.toml"

echo ""
echo "Syncing lock files..."
if command -v uv &>/dev/null; then
  (cd "$REPO_ROOT/surfsense_backend" && uv lock)
  echo "  OK    surfsense_backend/uv.lock"
else
  echo "  SKIP  uv not found -- run 'uv lock' in surfsense_backend/ manually"
fi

echo "---------------------------------"
echo "Done. All packages set to $VERSION"
