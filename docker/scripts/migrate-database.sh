#!/usr/bin/env bash
# =============================================================================
# SurfSense — Database Migration Script
#
# Extracts data from the legacy all-in-one surfsense-data volume (PostgreSQL 14)
# and saves it as a SQL dump + SECRET_KEY file ready for install.sh to restore.
#
# Usage:
#   bash migrate-database.sh [options]
#
# Options:
#   --db-user USER        Old PostgreSQL username   (default: surfsense)
#   --db-password PASS    Old PostgreSQL password   (default: surfsense)
#   --db-name NAME        Old PostgreSQL database   (default: surfsense)
#   --yes / -y            Skip all confirmation prompts
#   --help / -h           Show this help
#
# Prerequisites:
#   - Docker installed and running
#   - The legacy surfsense-data volume must exist
#   - ~500 MB free disk space for the dump file
#
# What this script does:
#   1. Stops any container using surfsense-data (to prevent corruption)
#   2. Starts a temporary PG14 container against the old volume
#   3. Dumps the database to ./surfsense_migration_backup.sql
#   4. Recovers the SECRET_KEY to ./surfsense_migration_secret.key
#   5. Exits — leaving installation to install.sh
#
# What this script does NOT do:
#   - Delete the original surfsense-data volume (do this manually after verifying)
#   - Install the new SurfSense stack (install.sh handles that automatically)
#
# Note:
#   install.sh downloads and runs this script automatically when it detects the
#   legacy surfsense-data volume. You only need to run this script manually if
#   you have custom database credentials (--db-user / --db-password / --db-name)
#   or if the automatic migration inside install.sh fails at the extraction step.
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# ── Logging — tee everything to a log file ───────────────────────────────────
LOG_FILE="./surfsense-migration.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

# ── Output helpers ────────────────────────────────────────────────────────────
info()    { printf "${CYAN}[SurfSense]${NC} %s\n"        "$1"; }
success() { printf "${GREEN}[SurfSense]${NC} %s\n"       "$1"; }
warn()    { printf "${YELLOW}[SurfSense]${NC} %s\n"      "$1"; }
error()   { printf "${RED}[SurfSense]${NC} ERROR: %s\n"  "$1" >&2; exit 1; }
step()    { printf "\n${BOLD}${CYAN}── Step %s: %s${NC}\n" "$1" "$2"; }

# ── Constants ─────────────────────────────────────────────────────────────────
OLD_VOLUME="surfsense-data"
TEMP_CONTAINER="surfsense-pg14-migration"
DUMP_FILE="./surfsense_migration_backup.sql"
KEY_FILE="./surfsense_migration_secret.key"
PG14_IMAGE="pgvector/pgvector:pg14"

# ── Defaults ──────────────────────────────────────────────────────────────────
OLD_DB_USER="surfsense"
OLD_DB_PASSWORD="surfsense"
OLD_DB_NAME="surfsense"
AUTO_YES=false

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-user)      OLD_DB_USER="$2";     shift 2 ;;
        --db-password)  OLD_DB_PASSWORD="$2"; shift 2 ;;
        --db-name)      OLD_DB_NAME="$2";     shift 2 ;;
        --yes|-y)       AUTO_YES=true;        shift   ;;
        --help|-h)
            grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) error "Unknown option: $1  — run with --help for usage." ;;
    esac
done

# ── Confirmation helper ───────────────────────────────────────────────────────
confirm() {
    if $AUTO_YES; then return 0; fi
    printf "${YELLOW}[SurfSense]${NC} %s [y/N] " "$1"
    read -r reply
    [[ "$reply" =~ ^[Yy]$ ]] || { warn "Aborted."; exit 0; }
}

# ── Cleanup trap — always remove the temp container ──────────────────────────
cleanup() {
    local exit_code=$?
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${TEMP_CONTAINER}$"; then
        info "Cleaning up temporary container '${TEMP_CONTAINER}'..."
        docker stop "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
        docker rm   "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
    fi
    if [[ $exit_code -ne 0 ]]; then
        printf "\n${RED}[SurfSense]${NC} Migration data extraction failed (exit code %s).\n" "${exit_code}" >&2
        printf "${RED}[SurfSense]${NC} Full log: %s\n" "${LOG_FILE}" >&2
        printf "${YELLOW}[SurfSense]${NC} Your original data in '${OLD_VOLUME}' is untouched.\n" >&2
    fi
}
trap cleanup EXIT

# ── Wait-for-postgres helper ──────────────────────────────────────────────────
wait_for_pg() {
    local container="$1"
    local user="$2"
    local label="${3:-PostgreSQL}"
    local max_attempts=45
    local attempt=0

    info "Waiting for ${label} to accept connections..."
    until docker exec "${container}" pg_isready -U "${user}" -q 2>/dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            error "${label} did not become ready after $((max_attempts * 2)) seconds. Check: docker logs ${container}"
        fi
        printf "."
        sleep 2
    done
    printf "\n"
    success "${label} is ready."
}

step "Migrating data from legacy database (PostgreSQL 14 → 17)"

# ── Step 0: Pre-flight checks ─────────────────────────────────────────────────
step "0" "Pre-flight checks"

# Docker CLI
command -v docker >/dev/null 2>&1 \
    || error "Docker is not installed. Install it at: https://docs.docker.com/get-docker/"

# Docker daemon
docker info >/dev/null 2>&1 \
    || error "Docker daemon is not running. Please start Docker and try again."

# Old volume must exist
docker volume ls --format '{{.Name}}' | grep -q "^${OLD_VOLUME}$" \
    || error "Legacy volume '${OLD_VOLUME}' not found.\n       Are you sure you ran the old all-in-one SurfSense container?"
success "Found legacy volume: ${OLD_VOLUME}"

# Detect and stop any container currently using the old volume
# (mounting a live PG volume into a second container causes the new container's
#  entrypoint to chown the data files, breaking the running container's access)
OLD_CONTAINER=$(docker ps --filter "volume=${OLD_VOLUME}" --format '{{.Names}}' | head -n1 || true)
if [[ -n "${OLD_CONTAINER}" ]]; then
    warn "Container '${OLD_CONTAINER}' is running and using the '${OLD_VOLUME}' volume."
    warn "It must be stopped before migration to prevent data file corruption."
    confirm "Stop '${OLD_CONTAINER}' now and proceed with data extraction?"
    docker stop "${OLD_CONTAINER}" >/dev/null 2>&1 \
        || error "Failed to stop '${OLD_CONTAINER}'. Try: docker stop ${OLD_CONTAINER}"
    success "Container '${OLD_CONTAINER}' stopped."
fi

# Bail out if a dump already exists — don't overwrite a previous successful run
if [[ -f "${DUMP_FILE}" ]]; then
    warn "Dump file '${DUMP_FILE}' already exists."
    warn "If a previous extraction succeeded, just run install.sh now."
    warn "To re-extract, remove the file first: rm ${DUMP_FILE}"
    error "Aborting to avoid overwriting an existing dump."
fi

# Clean up any stale temp container from a previous failed run
if docker ps -a --format '{{.Names}}' | grep -q "^${TEMP_CONTAINER}$"; then
    warn "Stale migration container '${TEMP_CONTAINER}' found — removing it."
    docker stop "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
    docker rm   "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
fi

# Disk space (warn if < 500 MB free)
if command -v df >/dev/null 2>&1; then
    FREE_KB=$(df -k . | awk 'NR==2 {print $4}')
    FREE_MB=$(( FREE_KB / 1024 ))
    if [[ $FREE_MB -lt 500 ]]; then
        warn "Low disk space: ${FREE_MB} MB free. At least 500 MB recommended for the dump."
        confirm "Continue anyway?"
    else
        success "Disk space: ${FREE_MB} MB free."
    fi
fi

success "All pre-flight checks passed."

# ── Confirmation prompt ───────────────────────────────────────────────────────
printf "\n${BOLD}Extraction plan:${NC}\n"
printf "  Source volume   : ${YELLOW}%s${NC}  (PG14 data at /data/postgres)\n" "${OLD_VOLUME}"
printf "  Old credentials : user=${YELLOW}%s${NC}  db=${YELLOW}%s${NC}\n" "${OLD_DB_USER}" "${OLD_DB_NAME}"
printf "  Dump saved to   : ${YELLOW}%s${NC}\n" "${DUMP_FILE}"
printf "  SECRET_KEY to   : ${YELLOW}%s${NC}\n" "${KEY_FILE}"
printf "  Log file        : ${YELLOW}%s${NC}\n\n" "${LOG_FILE}"
confirm "Start data extraction? (Your original data will not be deleted or modified.)"

# ── Step 1: Start temporary PostgreSQL 14 container ──────────────────────────
step "1" "Starting temporary PostgreSQL 14 container"

info "Pulling ${PG14_IMAGE}..."
docker pull "${PG14_IMAGE}" >/dev/null 2>&1 \
    || warn "Could not pull ${PG14_IMAGE} — using cached image if available."

# Detect the UID that owns the existing data files and run the temp container
# as that user. This prevents the official postgres image entrypoint from
# running as root and doing `chown -R postgres /data/postgres`, which would
# re-own the files to UID 999 and break any subsequent access by the original
# container's postgres process (which may run as a different UID).
DATA_UID=$(docker run --rm -v "${OLD_VOLUME}:/data" alpine \
    stat -c '%u' /data/postgres 2>/dev/null || echo "")
if [[ -z "${DATA_UID}" || "${DATA_UID}" == "0" ]]; then
    warn "Could not detect data directory UID — falling back to default (may chown files)."
    USER_FLAG=""
else
    info "Data directory owned by UID ${DATA_UID} — starting temp container as that user."
    USER_FLAG="--user ${DATA_UID}"
fi

docker run -d \
    --name "${TEMP_CONTAINER}" \
    -v "${OLD_VOLUME}:/data" \
    -e PGDATA=/data/postgres \
    -e POSTGRES_USER="${OLD_DB_USER}" \
    -e POSTGRES_PASSWORD="${OLD_DB_PASSWORD}" \
    -e POSTGRES_DB="${OLD_DB_NAME}" \
    ${USER_FLAG} \
    "${PG14_IMAGE}" >/dev/null

success "Temporary container '${TEMP_CONTAINER}' started."
wait_for_pg "${TEMP_CONTAINER}" "${OLD_DB_USER}" "PostgreSQL 14"

# ── Step 2: Dump the database ─────────────────────────────────────────────────
step "2" "Dumping PostgreSQL 14 database"

info "Running pg_dump — this may take a while for large databases..."

if ! docker exec \
        -e PGPASSWORD="${OLD_DB_PASSWORD}" \
        "${TEMP_CONTAINER}" \
        pg_dump -U "${OLD_DB_USER}" --no-password "${OLD_DB_NAME}" \
        > "${DUMP_FILE}" 2>/tmp/surfsense_pgdump_err; then
    cat /tmp/surfsense_pgdump_err >&2
    error "pg_dump failed. See above for details."
fi

# Validate: non-empty file
[[ -s "${DUMP_FILE}" ]] \
    || error "Dump file '${DUMP_FILE}' is empty. Something went wrong with pg_dump."

# Validate: looks like a real PG dump
grep -q "PostgreSQL database dump" "${DUMP_FILE}" \
    || error "Dump file does not contain a valid PostgreSQL dump header — the file may be corrupt."

# Validate: sanity-check line count
DUMP_LINES=$(wc -l < "${DUMP_FILE}" | tr -d ' ')
[[ $DUMP_LINES -ge 10 ]] \
    || error "Dump has only ${DUMP_LINES} lines — suspiciously small. Aborting."

DUMP_SIZE=$(du -sh "${DUMP_FILE}" 2>/dev/null | cut -f1)
success "Dump complete: ${DUMP_SIZE} (${DUMP_LINES} lines) → ${DUMP_FILE}"

# Stop the temp container (trap will also handle it on unexpected exit)
info "Stopping temporary PostgreSQL 14 container..."
docker stop "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
docker rm   "${TEMP_CONTAINER}" >/dev/null 2>&1 || true
success "Temporary container removed."

# ── Step 3: Recover SECRET_KEY ────────────────────────────────────────────────
step "3" "Recovering SECRET_KEY"

RECOVERED_KEY=""

if docker run --rm -v "${OLD_VOLUME}:/data" alpine \
        sh -c 'test -f /data/.secret_key && cat /data/.secret_key' \
        2>/dev/null | grep -q .; then
    RECOVERED_KEY=$(
        docker run --rm -v "${OLD_VOLUME}:/data" alpine \
            cat /data/.secret_key 2>/dev/null | tr -d '[:space:]'
    )
    success "Recovered SECRET_KEY from '${OLD_VOLUME}'."
else
    warn "No SECRET_KEY file found at /data/.secret_key in '${OLD_VOLUME}'."
    warn "This means the all-in-one container was launched with SECRET_KEY set as an explicit env var."
    if $AUTO_YES; then
        # Non-interactive (called from install.sh) — auto-generate rather than hanging on read
        RECOVERED_KEY=$(openssl rand -base64 32 2>/dev/null \
            || head -c 32 /dev/urandom | base64 | tr -d '\n')
        warn "Non-interactive mode: generated a new SECRET_KEY automatically."
        warn "All active browser sessions will be logged out after migration."
        warn "To restore your original key, update SECRET_KEY in ./surfsense/.env afterwards."
    else
        printf "${YELLOW}[SurfSense]${NC} Enter the SECRET_KEY from your old container's environment\n"
        printf "${YELLOW}[SurfSense]${NC} (press Enter to generate a new one — existing sessions will be invalidated): "
        read -r RECOVERED_KEY
        if [[ -z "${RECOVERED_KEY}" ]]; then
            RECOVERED_KEY=$(openssl rand -base64 32 2>/dev/null \
                || head -c 32 /dev/urandom | base64 | tr -d '\n')
            warn "Generated a new SECRET_KEY. All active browser sessions will be logged out after migration."
        fi
    fi
fi

# Save SECRET_KEY to a file for install.sh to pick up
printf '%s' "${RECOVERED_KEY}" > "${KEY_FILE}"
success "SECRET_KEY saved to ${KEY_FILE}"

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n${GREEN}${BOLD}"
printf "══════════════════════════════════════════════════════════════\n"
printf "  Data extraction complete!\n"
printf "══════════════════════════════════════════════════════════════\n"
printf "${NC}\n"

success "Dump file : ${DUMP_FILE}  (${DUMP_SIZE})"
success "Secret key: ${KEY_FILE}"
printf "\n"
info "Next step — run install.sh from this same directory:"
printf "\n"
printf "${CYAN}  curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash${NC}\n"
printf "\n"
info "install.sh will detect the dump, restore your data into PostgreSQL 17,"
info "and start the full SurfSense stack automatically."
printf "\n"
warn "Keep both files until you have verified the migration:"
warn "  ${DUMP_FILE}"
warn "  ${KEY_FILE}"
warn "Full log saved to: ${LOG_FILE}"
printf "\n"
