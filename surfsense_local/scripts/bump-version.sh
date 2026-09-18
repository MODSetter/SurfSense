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
TS_FIELD='^export const APP_RELEASE_VERSION = "[^"]*"'
PY_FIELD='^APP_RELEASE_VERSION = "[^"]*"'

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "ERROR: python3 is required to rewrite version fields" >&2
  exit 1
fi

echo "Bumping surfsense_local to $VERSION"
echo "---------------------------------"

# ponytail: GNU `sed -i` is not BSD or Windows; CPython is already on the
# Mac/Linux/Windows machines that cut this release. Ceiling: POSIX `[[:space:]]`
# in the grep patterns is mapped to `\s` here — upgrade if a field needs a
# real character class.
rewrite_first() {
  "$PYTHON" - "$1" "$2" "$3" <<'PY'
import pathlib, re, sys

path, field, replacement = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
pattern = field.replace("[[:space:]]", r"\s")
text = path.read_text(encoding="utf-8")
new, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
if n != 1:
    raise SystemExit(f"no version field match in {path}")
path.write_text(new, encoding="utf-8")
PY
}

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

  rewrite_first "$file" "$field" "$replacement"

  if ! grep -qF "$replacement" "$file"; then
    echo "ERROR: failed to rewrite version in $file" >&2
    exit 1
  fi
  echo "  SET   $file ($old -> $VERSION)"
}

bump "$LOCAL_ROOT/backend/pyproject.toml" "$TOML_FIELD" "version = \"$VERSION\""
bump "$LOCAL_ROOT/frontend/package.json" "$JSON_FIELD" "\"version\": \"$VERSION\""
bump "$LOCAL_ROOT/electron/package.json" "$JSON_FIELD" "\"version\": \"$VERSION\""
bump "$LOCAL_ROOT/../surfsense_web/lib/app-release.ts" "$TS_FIELD" \
  "export const APP_RELEASE_VERSION = \"$VERSION\""
bump "$LOCAL_ROOT/../surfsense_backend/app/license/release.py" "$PY_FIELD" \
  "APP_RELEASE_VERSION = \"$VERSION\""

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
