#!/usr/bin/env bash
# =============================================================================
# SurfSense — One-line Install Script
#
#
# Usage: curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
#
# Flags:
#   --no-watchtower              Skip automatic Watchtower setup
#   --watchtower-interval=SECS   Check interval in seconds (default: 86400 = 24h)
#
# Handles two cases automatically:
#   1. Fresh install        — no prior SurfSense data detected
#   2. Migration from the legacy all-in-one container (surfsense-data volume)
#      Downloads and runs migrate-database.sh --yes, then restores the dump
#      into the new PostgreSQL 17 stack. The user runs one command for both.
#
# If you used custom database credentials in the old all-in-one container, run
# migrate-database.sh manually first (with --db-user / --db-password flags),
# then re-run this script:
#   curl -fsSL .../docker/scripts/migrate-database.sh | bash -s -- --db-user X --db-password Y
# =============================================================================

set -euo pipefail

main() {

REPO_RAW="https://raw.githubusercontent.com/MODSetter/SurfSense/main"
INSTALL_DIR="./surfsense"
OLD_VOLUME="surfsense-data"
DUMP_FILE="./surfsense_migration_backup.sql"
KEY_FILE="./surfsense_migration_secret.key"
MIGRATION_DONE_FILE="${INSTALL_DIR}/.migration_done"
MIGRATION_MODE=false
SETUP_WATCHTOWER=true
WATCHTOWER_INTERVAL=86400
WATCHTOWER_CONTAINER="watchtower"

# ── Parse flags ─────────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --no-watchtower) SETUP_WATCHTOWER=false ;;
        --watchtower-interval=*) WATCHTOWER_INTERVAL="${arg#*=}" ;;
    esac
done

CYAN='\033[1;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${CYAN}[SurfSense]${NC} %s\n"        "$1"; }
success() { printf "${GREEN}[SurfSense]${NC} %s\n"       "$1"; }
warn()    { printf "${YELLOW}[SurfSense]${NC} %s\n"      "$1"; }
error()   { printf "${RED}[SurfSense]${NC} ERROR: %s\n"  "$1" >&2; exit 1; }
step()    { printf "\n${BOLD}${CYAN}── %s${NC}\n"        "$1"; }

# ── Pre-flight checks ────────────────────────────────────────────────────────

step "Checking prerequisites"

command -v docker >/dev/null 2>&1 \
    || error "Docker is not installed. Install it at: https://docs.docker.com/get-docker/"
success "Docker found."

docker info >/dev/null 2>&1 < /dev/null \
    || error "Docker daemon is not running. Please start Docker and try again."
success "Docker daemon is running."

if docker compose version >/dev/null 2>&1 < /dev/null; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    error "Docker Compose is not installed. Install it at: https://docs.docker.com/compose/install/"
fi
success "Docker Compose found ($DC)."

# ── Wait-for-postgres helper ─────────────────────────────────────────────────
wait_for_pg() {
    local db_user="$1"
    local max_attempts=45
    local attempt=0

    info "Waiting for PostgreSQL to accept connections..."
    until (cd "${INSTALL_DIR}" && ${DC} exec -T db pg_isready -U "${db_user}" -q 2>/dev/null) < /dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            error "PostgreSQL did not become ready after $((max_attempts * 2)) seconds.\nCheck logs: cd ${INSTALL_DIR} && ${DC} logs db"
        fi
        printf "."
        sleep 2
    done
    printf "\n"
    success "PostgreSQL is ready."
}

# ── Download files ───────────────────────────────────────────────────────────

step "Downloading SurfSense files"
info "Installation directory: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/scripts"
mkdir -p "${INSTALL_DIR}/searxng"

FILES=(
    "docker/docker-compose.yml:docker-compose.yml"
    "docker/.env.example:.env.example"
    "docker/postgresql.conf:postgresql.conf"
    "docker/scripts/migrate-database.sh:scripts/migrate-database.sh"
    "docker/searxng/settings.yml:searxng/settings.yml"
    "docker/searxng/limiter.toml:searxng/limiter.toml"
)

for entry in "${FILES[@]}"; do
    src="${entry%%:*}"
    dest="${entry##*:}"
    info "Downloading ${dest}..."
    curl -fsSL "${REPO_RAW}/${src}" -o "${INSTALL_DIR}/${dest}" \
        || error "Failed to download ${dest}. Check your internet connection and try again."
done

chmod +x "${INSTALL_DIR}/scripts/migrate-database.sh"
success "All files downloaded to ${INSTALL_DIR}/"

# ── Legacy all-in-one detection ──────────────────────────────────────────────
# Detect surfsense-data volume → migration mode.
# If a dump already exists (from a previous partial run) skip extraction and
# go straight to restore — this makes re-runs safe and idempotent.

if docker volume ls --format '{{.Name}}' 2>/dev/null < /dev/null | grep -q "^${OLD_VOLUME}$" \
   && [[ ! -f "${MIGRATION_DONE_FILE}" ]]; then
    MIGRATION_MODE=true

    if [[ -f "${DUMP_FILE}" ]]; then
        step "Migration mode — using existing dump (skipping extraction)"
        info "Found existing dump: ${DUMP_FILE}"
        info "Skipping data extraction — proceeding directly to restore."
        info "To force a fresh extraction, remove the dump first: rm ${DUMP_FILE}"
    else
        step "Migration mode — legacy all-in-one container detected"
        warn "Volume '${OLD_VOLUME}' found. Your data will be migrated automatically."
        warn "PostgreSQL is being upgraded from version 14 to 17."
        warn "Your original data will NOT be deleted."
        printf "\n"
        info "Running data extraction (migrate-database.sh --yes)..."
        info "Full extraction log: ./surfsense-migration.log"
        printf "\n"

        # Run extraction non-interactively. On failure the error from
        # migrate-database.sh is printed and install.sh exits here.
        bash "${INSTALL_DIR}/scripts/migrate-database.sh" --yes < /dev/null \
            || error "Data extraction failed. See ./surfsense-migration.log for details.\nYou can also run migrate-database.sh manually with custom flags:\n  bash ${INSTALL_DIR}/scripts/migrate-database.sh --db-user X --db-password Y"

        printf "\n"
        success "Data extraction complete. Proceeding with installation and restore."
    fi
fi

# ── Set up .env ──────────────────────────────────────────────────────────────

step "Configuring environment"

if [ ! -f "${INSTALL_DIR}/.env" ]; then
    cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"

    if $MIGRATION_MODE && [[ -f "${KEY_FILE}" ]]; then
        SECRET_KEY=$(cat "${KEY_FILE}" | tr -d '[:space:]')
        success "Using SECRET_KEY recovered from legacy container."
    else
        SECRET_KEY=$(openssl rand -base64 32 2>/dev/null \
            || head -c 32 /dev/urandom | base64 | tr -d '\n')
        success "Generated new random SECRET_KEY."
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${SECRET_KEY}|" "${INSTALL_DIR}/.env"
    else
        sed -i "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${SECRET_KEY}|" "${INSTALL_DIR}/.env"
    fi
    info "Created ${INSTALL_DIR}/.env"
else
    warn ".env already exists — keeping your existing configuration."
fi

# ── Start containers ─────────────────────────────────────────────────────────

if $MIGRATION_MODE; then
    # Read DB credentials from .env (fall back to defaults from docker-compose.yml)
    DB_USER=$(grep '^DB_USER=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1 || true)
    DB_PASS=$(grep '^DB_PASSWORD=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1 || true)
    DB_NAME=$(grep '^DB_NAME=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1 || true)
    DB_USER="${DB_USER:-surfsense}"
    DB_PASS="${DB_PASS:-surfsense}"
    DB_NAME="${DB_NAME:-surfsense}"

    step "Starting PostgreSQL 17"
    (cd "${INSTALL_DIR}" && ${DC} up -d db) < /dev/null
    wait_for_pg "${DB_USER}"

    step "Restoring database"
    [[ -f "${DUMP_FILE}" ]] \
        || error "Dump file '${DUMP_FILE}' not found. The migration script may have failed.\n  Check: ./surfsense-migration.log\n  Or run manually: bash ${INSTALL_DIR}/scripts/migrate-database.sh --yes"
    info "Restoring dump into PostgreSQL 17 — this may take a while for large databases..."

    RESTORE_ERR="/tmp/surfsense_restore_err.log"
    (cd "${INSTALL_DIR}" && ${DC} exec -T \
        -e PGPASSWORD="${DB_PASS}" \
        db psql -U "${DB_USER}" -d "${DB_NAME}" \
        >/dev/null 2>"${RESTORE_ERR}") < "${DUMP_FILE}" || true

    # Surface real errors; ignore benign "already exists" noise from pg_dump headers
    FATAL_ERRORS=$(grep -i "^ERROR:" "${RESTORE_ERR}" \
        | grep -iv "already exists" \
        | grep -iv "multiple primary keys" \
        || true)

    if [[ -n "${FATAL_ERRORS}" ]]; then
        warn "Restore completed with errors (may be harmless pg_dump header noise):"
        printf "%s\n" "${FATAL_ERRORS}"
        warn "If SurfSense behaves incorrectly, inspect manually:"
        warn "  cd ${INSTALL_DIR} && ${DC} exec db psql -U ${DB_USER} -d ${DB_NAME} < ${DUMP_FILE}"
    else
        success "Database restored with no fatal errors."
    fi

    # Smoke test — verify tables are present
    TABLE_COUNT=$(
        cd "${INSTALL_DIR}" && ${DC} exec -T \
            -e PGPASSWORD="${DB_PASS}" \
            db psql -U "${DB_USER}" -d "${DB_NAME}" -t \
            -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
            2>/dev/null < /dev/null | tr -d ' \n' || echo "0"
    )
    if [[ "${TABLE_COUNT}" == "0" || -z "${TABLE_COUNT}" ]]; then
        warn "Smoke test: no tables found after restore."
        warn "The restore may have failed silently. Check: cd ${INSTALL_DIR} && ${DC} logs db"
    else
        success "Smoke test passed: ${TABLE_COUNT} table(s) restored successfully."
        touch "${MIGRATION_DONE_FILE}"
    fi

    step "Starting all SurfSense services"
    (cd "${INSTALL_DIR}" && ${DC} up -d) < /dev/null
    success "All services started."

    # Key file is no longer needed — SECRET_KEY is now in .env
    rm -f "${KEY_FILE}"

else
    step "Starting SurfSense"
    (cd "${INSTALL_DIR}" && ${DC} up -d) < /dev/null
    success "All services started."
fi

# ── Watchtower (auto-update) ─────────────────────────────────────────────────

if $SETUP_WATCHTOWER; then
    step "Setting up Watchtower (auto-updates every $((WATCHTOWER_INTERVAL / 3600))h)"

    WT_STATE=$(docker inspect -f '{{.State.Running}}' "${WATCHTOWER_CONTAINER}" 2>/dev/null < /dev/null || echo "missing")

    if [[ "${WT_STATE}" == "true" ]]; then
        success "Watchtower is already running — skipping."
    else
        if [[ "${WT_STATE}" != "missing" ]]; then
            info "Removing stopped Watchtower container..."
            docker rm -f "${WATCHTOWER_CONTAINER}" >/dev/null 2>&1 < /dev/null || true
        fi
        docker run -d \
            --name "${WATCHTOWER_CONTAINER}" \
            --restart unless-stopped \
            -v /var/run/docker.sock:/var/run/docker.sock \
            nickfedor/watchtower \
            --label-enable \
            --interval "${WATCHTOWER_INTERVAL}" >/dev/null 2>&1 < /dev/null \
            && success "Watchtower started — labeled SurfSense containers will auto-update." \
            || warn "Could not start Watchtower. You can set it up manually or use: docker compose pull && docker compose up -d"
    fi
else
    info "Skipping Watchtower setup (--no-watchtower flag)."
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
printf '\033[1;37m'
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
_version_display=$(grep '^SURFSENSE_VERSION=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1 || true)
_version_display="${_version_display:-latest}"
printf "         OSS Alternative to NotebookLM for Teams  ${YELLOW}[%s]${NC}\n" "${_version_display}"
printf "${CYAN}══════════════════════════════════════════════════════════════${NC}\n\n"

info "  Frontend:  http://localhost:3929"
info "  Backend:   http://localhost:8929"
info "  API Docs:  http://localhost:8929/docs"
info ""
info "  Config:    ${INSTALL_DIR}/.env"
info "  Logs:      cd ${INSTALL_DIR} && ${DC} logs -f"
info "  Stop:      cd ${INSTALL_DIR} && ${DC} down"
info "  Update:    cd ${INSTALL_DIR} && ${DC} pull && ${DC} up -d"
info ""

if $SETUP_WATCHTOWER; then
    info "  Watchtower: auto-updates every $((WATCHTOWER_INTERVAL / 3600))h (stop: docker rm -f ${WATCHTOWER_CONTAINER})"
else
    warn "  Watchtower skipped. For auto-updates, re-run without --no-watchtower."
fi
info ""

if $MIGRATION_MODE; then
    warn "  Migration complete! Open frontend and verify your data."
    warn "  Once verified, clean up the legacy volume and migration files:"
    warn "    docker volume rm ${OLD_VOLUME}"
    warn "    rm ${DUMP_FILE}"
    warn "    rm ${MIGRATION_DONE_FILE}"
else
    warn "  First startup may take a few minutes while images are pulled."
    warn "  Edit ${INSTALL_DIR}/.env to configure API keys, OAuth, etc."
fi

} # end main()

main "$@"
