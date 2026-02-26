#!/usr/bin/env bash
# =============================================================================
# SurfSense — Database Migration Script
#
# Migrates data from the legacy all-in-one surfsense-data volume (PostgreSQL 14)
# to the new multi-container surfsense-postgres volume (PostgreSQL 17) using
# a logical pg_dump / psql restore — safe across major PG versions.
#
# Usage:
#   bash migrate-database.sh [options]
#
# Options:
#   --db-user USER        Old PostgreSQL username   (default: surfsense)
#   --db-password PASS    Old PostgreSQL password   (default: surfsense)
#   --db-name NAME        Old PostgreSQL database   (default: surfsense)
#   --install-dir DIR     New installation directory (default: ./surfsense)
#   --yes / -y            Skip all confirmation prompts
#   --help / -h           Show this help
#
# Prerequisites:
#   - Docker and Docker Compose installed and running
#   - The legacy surfsense-data volume must exist
#   - ~500 MB free disk space for the dump file
#
# What this script does NOT do:
#   - Delete the original surfsense-data volume (you must do this manually
#     after verifying the migration succeeded)
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
REPO_RAW="https://raw.githubusercontent.com/MODSetter/SurfSense/main"
OLD_VOLUME="surfsense-data"
NEW_PG_VOLUME="surfsense-postgres"
TEMP_CONTAINER="surfsense-pg14-migration"
DUMP_FILE="./surfsense_migration_backup.sql"
PG14_IMAGE="postgres:14"

# ── Defaults ──────────────────────────────────────────────────────────────────
OLD_DB_USER="surfsense"
OLD_DB_PASSWORD="surfsense"
OLD_DB_NAME="surfsense"
INSTALL_DIR="./surfsense"
AUTO_YES=false

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-user)      OLD_DB_USER="$2";     shift 2 ;;
        --db-password)  OLD_DB_PASSWORD="$2"; shift 2 ;;
        --db-name)      OLD_DB_NAME="$2";     shift 2 ;;
        --install-dir)  INSTALL_DIR="$2";     shift 2 ;;
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
        printf "\n${RED}[SurfSense]${NC} Migration failed (exit code %s).\n" "${exit_code}" >&2
        printf "${RED}[SurfSense]${NC} Full log: %s\n" "${LOG_FILE}" >&2
        printf "${YELLOW}[SurfSense]${NC} Your original data in '${OLD_VOLUME}' is untouched.\n" >&2
    fi
}
trap cleanup EXIT

# ── Wait-for-postgres helper ──────────────────────────────────────────────────
# $1 = container name/id  $2 = db user  $3 = label for messages
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
            error "${label} did not become ready after $((max_attempts * 2)) seconds.\nCheck logs: docker logs ${container}"
        fi
        printf "."
        sleep 2
    done
    printf "\n"
    success "${label} is ready."
}

# ── Banner ────────────────────────────────────────────────────────────────────
printf "\n${BOLD}${CYAN}"
cat << 'EOF'


 .d8888b.                    .d888 .d8888b.                                      
d88P  Y88b                  d88P" d88P  Y88b                                     
Y88b.                       888   Y88b.                                          
 "Y888b.   888  888 888d888 888888 "Y888b.    .d88b.  88888b.  .d8888b   .d88b.  
    "Y88b. 888  888 888P"   888       "Y88b. d8P  Y8b 888 "88b 88K      d8P  Y8b 
      "888 888  888 888     888         "888 88888888 888  888 "Y8888b. 88888888 
Y88b  d88P Y88b 888 888     888   Y88b  d88P Y8b.     888  888      X88 Y8b.     
 "Y8888P"   "Y88888 888     888    "Y8888P"   "Y8888  888  888  88888P'  "Y8888  


EOF
printf "${NC}"
printf "${CYAN}  Database Migration: All-in-One → Multi-Container (PG 14 → 17)${NC}\n"
printf "${CYAN}══════════════════════════════════════════════════════════════${NC}\n\n"

# ── Step 0: Pre-flight checks ─────────────────────────────────────────────────
step "0" "Pre-flight checks"

# Docker CLI
command -v docker >/dev/null 2>&1 \
    || error "Docker is not installed. Install it at: https://docs.docker.com/get-docker/"

# Docker daemon
docker info >/dev/null 2>&1 \
    || error "Docker daemon is not running. Please start Docker and try again."

# Docker Compose
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    error "Docker Compose not found. Install it at: https://docs.docker.com/compose/install/"
fi
info "Docker Compose: ${DC}"

# OS detection (needed for sed -i portability)
case "$(uname -s)" in
    Darwin*) OS_TYPE="darwin" ;;
    Linux*)  OS_TYPE="linux"  ;;
    CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;;
    *) OS_TYPE="unknown" ;;
esac
info "OS: ${OS_TYPE}"

# Old volume must exist
docker volume ls --format '{{.Name}}' | grep -q "^${OLD_VOLUME}$" \
    || error "Legacy volume '${OLD_VOLUME}' not found.\n       Are you sure you ran the old all-in-one SurfSense container?"
success "Found legacy volume: ${OLD_VOLUME}"

# New PG volume must NOT already exist
if docker volume ls --format '{{.Name}}' | grep -q "^${NEW_PG_VOLUME}$"; then
    warn "Volume '${NEW_PG_VOLUME}' already exists."
    warn "If migration already succeeded, you do not need to run this script again."
    warn "If a previous run failed partway, remove the partial volume first:"
    warn "  docker volume rm ${NEW_PG_VOLUME}"
    error "Aborting to avoid overwriting existing data."
fi
success "Target volume '${NEW_PG_VOLUME}' does not yet exist — safe to proceed."

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
printf "\n${BOLD}Migration plan:${NC}\n"
printf "  Source volume   : ${YELLOW}%s${NC}  (PG14 data at /data/postgres)\n" "${OLD_VOLUME}"
printf "  Target volume   : ${YELLOW}%s${NC}  (PG17 multi-container stack)\n" "${NEW_PG_VOLUME}"
printf "  Old credentials : user=${YELLOW}%s${NC}  db=${YELLOW}%s${NC}\n" "${OLD_DB_USER}" "${OLD_DB_NAME}"
printf "  Install dir     : ${YELLOW}%s${NC}\n" "${INSTALL_DIR}"
printf "  Dump saved to   : ${YELLOW}%s${NC}\n" "${DUMP_FILE}"
printf "  Log file        : ${YELLOW}%s${NC}\n\n" "${LOG_FILE}"
confirm "Start migration? (Your original data will not be deleted.)"

# ── Step 1: Start temporary PostgreSQL 14 container ──────────────────────────
step "1" "Starting temporary PostgreSQL 14 container"

info "Pulling ${PG14_IMAGE}..."
docker pull "${PG14_IMAGE}" >/dev/null 2>&1 \
    || warn "Could not pull ${PG14_IMAGE} — using cached image if available."

docker run -d \
    --name "${TEMP_CONTAINER}" \
    -v "${OLD_VOLUME}:/data" \
    -e PGDATA=/data/postgres \
    -e POSTGRES_USER="${OLD_DB_USER}" \
    -e POSTGRES_PASSWORD="${OLD_DB_PASSWORD}" \
    -e POSTGRES_DB="${OLD_DB_NAME}" \
    "${PG14_IMAGE}" >/dev/null

success "Temporary container '${TEMP_CONTAINER}' started."
wait_for_pg "${TEMP_CONTAINER}" "${OLD_DB_USER}" "PostgreSQL 14"

# ── Step 2: Dump the database ─────────────────────────────────────────────────
step "2" "Dumping PostgreSQL 14 database"

info "Running pg_dump — this may take a while for large databases..."

# Run pg_dump and capture stderr separately to detect real failures
if ! docker exec \
        -e PGPASSWORD="${OLD_DB_PASSWORD}" \
        "${TEMP_CONTAINER}" \
        pg_dump -U "${OLD_DB_USER}" --no-password "${OLD_DB_NAME}" \
        > "${DUMP_FILE}" 2>/tmp/pg_dump_err; then
    cat /tmp/pg_dump_err >&2
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

# Stop the temp container now (trap will also handle it on unexpected exit)
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
    warn "This means the all-in-one was launched with SECRET_KEY set as an explicit environment variable."
    printf "${YELLOW}[SurfSense]${NC} Enter the SECRET_KEY from your old container's environment\n"
    printf "${YELLOW}[SurfSense]${NC} (press Enter to generate a new one — existing sessions will be invalidated): "
    read -r RECOVERED_KEY
    if [[ -z "${RECOVERED_KEY}" ]]; then
        RECOVERED_KEY=$(openssl rand -base64 32 2>/dev/null \
            || head -c 32 /dev/urandom | base64 | tr -d '\n')
        warn "Generated a new SECRET_KEY. All active browser sessions will be logged out after migration."
    fi
fi

# ── Step 4: Set up the new installation ───────────────────────────────────────
step "4" "Setting up new SurfSense installation"

if [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
    warn "Directory '${INSTALL_DIR}' already exists — skipping file download."
else
    info "Creating installation directory: ${INSTALL_DIR}"
    mkdir -p "${INSTALL_DIR}/scripts"

    FILES=(
        "docker/docker-compose.yml:docker-compose.yml"
        "docker/.env.example:.env.example"
        "docker/postgresql.conf:postgresql.conf"
        "docker/scripts/init-electric-user.sh:scripts/init-electric-user.sh"
    )

    for entry in "${FILES[@]}"; do
        src="${entry%%:*}"
        dest="${entry##*:}"
        info "Downloading ${dest}..."
        curl -fsSL "${REPO_RAW}/${src}" -o "${INSTALL_DIR}/${dest}" \
            || error "Failed to download ${src}. Check your internet connection."
    done

    chmod +x "${INSTALL_DIR}/scripts/init-electric-user.sh"
    success "Compose files downloaded to ${INSTALL_DIR}/"
fi

# Create .env from example if it does not exist
if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
    info "Created ${INSTALL_DIR}/.env from .env.example"
fi

# Write the recovered SECRET_KEY into .env (handles both placeholder and pre-set values)
if [[ "${OS_TYPE}" == "darwin" ]]; then
    sed -i '' "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${RECOVERED_KEY}|" "${INSTALL_DIR}/.env"
    sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=${RECOVERED_KEY}|"                              "${INSTALL_DIR}/.env"
else
    sed -i "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${RECOVERED_KEY}|"    "${INSTALL_DIR}/.env"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${RECOVERED_KEY}|"                                 "${INSTALL_DIR}/.env"
fi
success "SECRET_KEY written to ${INSTALL_DIR}/.env"

# ── Step 5: Start PostgreSQL 17 (new stack) ───────────────────────────────────
step "5" "Starting PostgreSQL 17"

(cd "${INSTALL_DIR}" && ${DC} up -d db)

# Resolve the running container name for direct docker exec calls
PG17_CONTAINER=$(cd "${INSTALL_DIR}" && ${DC} ps -q db 2>/dev/null | head -n1 || true)
if [[ -z "${PG17_CONTAINER}" ]]; then
    # Fallback to the predictable compose container name
    PG17_CONTAINER="surfsense-db-1"
fi
info "PostgreSQL 17 container: ${PG17_CONTAINER}"

wait_for_pg "${PG17_CONTAINER}" "${OLD_DB_USER}" "PostgreSQL 17"

# ── Step 6: Restore the dump ──────────────────────────────────────────────────
step "6" "Restoring database into PostgreSQL 17"

info "Running psql restore — this may take a while for large databases..."

RESTORE_ERR_FILE="/tmp/surfsense_restore_err.log"

docker exec -i \
    -e PGPASSWORD="${OLD_DB_PASSWORD}" \
    "${PG17_CONTAINER}" \
    psql -U "${OLD_DB_USER}" -d "${OLD_DB_NAME}" \
    < "${DUMP_FILE}" \
    2>"${RESTORE_ERR_FILE}" || true   # psql exits non-zero on warnings; check below

# Surface any real (non-benign) errors
FATAL_ERRORS=$(grep -i "^ERROR:" "${RESTORE_ERR_FILE}" \
    | grep -iv "already exists" \
    | grep -iv "multiple primary keys" \
    || true)

if [[ -n "${FATAL_ERRORS}" ]]; then
    warn "Restore completed with the following errors:"
    printf "%s\n" "${FATAL_ERRORS}"
    confirm "These may be harmless (e.g. pre-existing system objects). Continue?"
else
    success "Restore completed with no fatal errors."
fi

# Smoke test — verify tables exist in the restored database
TABLE_COUNT=$(
    docker exec \
        -e PGPASSWORD="${OLD_DB_PASSWORD}" \
        "${PG17_CONTAINER}" \
        psql -U "${OLD_DB_USER}" -d "${OLD_DB_NAME}" -t \
        -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
        2>/dev/null | tr -d ' \n' || echo "0"
)

if [[ "${TABLE_COUNT}" == "0" || -z "${TABLE_COUNT}" ]]; then
    warn "Smoke test: no tables found in the restored database."
    warn "The restore may have failed silently. Inspect the dump and restore manually:"
    warn "  docker exec -i ${PG17_CONTAINER} psql -U ${OLD_DB_USER} -d ${OLD_DB_NAME} < ${DUMP_FILE}"
    confirm "Continue starting the rest of the stack anyway?"
else
    success "Smoke test passed: ${TABLE_COUNT} table(s) found in the restored database."
fi

# ── Step 7: Start all remaining services ──────────────────────────────────────
step "7" "Starting all SurfSense services"

(cd "${INSTALL_DIR}" && ${DC} up -d)
success "All services started."

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n${GREEN}${BOLD}"
printf "══════════════════════════════════════════════════════════════\n"
printf "  Migration complete!\n"
printf "══════════════════════════════════════════════════════════════\n"
printf "${NC}\n"

success "  Frontend : http://localhost:3000"
success "  Backend  : http://localhost:8000"
success "  API Docs : http://localhost:8000/docs"
printf "\n"
info "  Config   : ${INSTALL_DIR}/.env"
info "  Logs     : cd ${INSTALL_DIR} && ${DC} logs -f"
printf "\n"
warn "Next steps:"
warn "  1. Open http://localhost:3000 and verify your data is intact."
warn "  2. Once satisfied, remove the legacy volume (IRREVERSIBLE):"
warn "       docker volume rm ${OLD_VOLUME}"
warn "  3. Delete the dump file once you no longer need it as a backup:"
warn "       rm ${DUMP_FILE}"
warn "  Full migration log saved to: ${LOG_FILE}"
printf "\n"
