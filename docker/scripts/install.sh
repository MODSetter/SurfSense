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

# ── Stack health helpers ─────────────────────────────────────────────────────

# Enumerate compose services for project `surfsense` as `service|state|health|exitcode`
# lines. Uses `docker inspect` so we don't depend on `jq`, `python3`, or the
# exact ordering of fields in `docker compose ps --format json` output.
get_compose_services() {
    local containers
    containers=$(docker ps -a --filter "label=com.docker.compose.project=surfsense" --format '{{.Names}}' 2>/dev/null) || true
    [[ -z "$containers" ]] && return 0

    while IFS= read -r container; do
        [[ -z "$container" ]] && continue
        local svc state health code
        svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$container" 2>/dev/null || echo "")
        state=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
        health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container" 2>/dev/null || echo "")
        code=$(docker inspect -f '{{.State.ExitCode}}' "$container" 2>/dev/null || echo "")
        [[ -z "$svc" ]] && continue
        printf '%s|%s|%s|%s\n' "$svc" "$state" "$health" "$code"
    done <<< "$containers"
}

# Globals populated by wait_stack_healthy / consumed by stack_failure_report.
STACK_BAD=()
STACK_WAITING=()
STACK_GOOD=()
STACK_TIMEOUT=false

wait_stack_healthy() {
    local timeout_sec=${1:-300}
    local deadline=$(($(date +%s) + timeout_sec))
    local last_report=""
    local bad=()
    local waiting=()
    local good=()

    while [[ $(date +%s) -lt $deadline ]]; do
        local lines
        lines=$(get_compose_services)
        if [[ -z "$lines" ]]; then
            sleep 3
            continue
        fi

        bad=()
        waiting=()
        good=()

        while IFS='|' read -r name state health code; do
            [[ -z "$name" ]] && continue
            if [[ "$name" == "migrations" ]]; then
                if [[ "$state" == "exited" && "$code" == "0" ]]; then
                    good+=("$name")
                elif [[ "$state" == "exited" ]]; then
                    bad+=("${name} (exit=${code})")
                else
                    waiting+=("${name} (${state})")
                fi
                continue
            fi

            if [[ "$state" == "running" ]]; then
                if [[ -z "$health" || "$health" == "healthy" ]]; then
                    good+=("$name")
                elif [[ "$health" == "starting" ]]; then
                    waiting+=("${name} (starting)")
                elif [[ "$health" == "unhealthy" ]]; then
                    bad+=("${name} (unhealthy)")
                else
                    waiting+=("${name} (${health})")
                fi
            elif [[ "$state" == "restarting" ]]; then
                bad+=("${name} (restarting)")
            elif [[ "$state" == "exited" ]]; then
                bad+=("${name} (exited, code=${code})")
            else
                waiting+=("${name} (${state})")
            fi
        done <<< "$lines"

        if (( ${#bad[@]} > 0 )); then
            STACK_BAD=("${bad[@]}")
            STACK_WAITING=("${waiting[@]}")
            STACK_GOOD=("${good[@]}")
            return 1
        fi
        if (( ${#waiting[@]} == 0 )); then
            STACK_GOOD=("${good[@]}")
            return 0
        fi

        local report="Waiting on: ${waiting[*]}"
        if [[ "$report" != "$last_report" ]]; then
            info "$report"
            last_report="$report"
        fi
        sleep 5
    done

    # bad/waiting/good are declared at function scope so referencing them is
    # safe even if the polling loop never executed its body.
    STACK_BAD=()
    [[ ${#bad[@]} -gt 0 ]] && STACK_BAD=("${bad[@]}")
    STACK_WAITING=()
    [[ ${#waiting[@]} -gt 0 ]] && STACK_WAITING=("${waiting[@]}")
    STACK_GOOD=()
    [[ ${#good[@]} -gt 0 ]] && STACK_GOOD=("${good[@]}")
    STACK_TIMEOUT=true
    return 1
}

stack_failure_report() {
    echo ""
    echo -e "\033[31m[ERROR]\033[0m Stack did not reach a healthy state."
    if (( ${#STACK_BAD[@]} > 0 )) && [[ -n "${STACK_BAD[0]}" ]]; then
        echo "  Failed: ${STACK_BAD[*]}"
    fi
    if (( ${#STACK_WAITING[@]} > 0 )) && [[ -n "${STACK_WAITING[0]}" ]]; then
        echo "  Stuck:  ${STACK_WAITING[*]}"
    fi
    echo ""
    info "Recent logs from migrations / zero-cache / backend:"
    (cd "${INSTALL_DIR}" && ${DC} logs --tail=60 migrations zero-cache backend 2>&1) || true
    echo ""
    echo "Recovery hints:"
    echo "  1. Inspect migrations:   cd ${INSTALL_DIR} && ${DC} logs migrations"
    echo "  2. Verify publication:   cd ${INSTALL_DIR} && ${DC} exec db psql -U surfsense -d surfsense -c 'SELECT pubname FROM pg_publication;'"
    echo "  3. Hard reset zero db:   cd ${INSTALL_DIR} && ${DC} down && docker volume rm surfsense-zero-cache && ${DC} up -d"
    echo ""
    exit 1
}

# True if `surfsense-zero-cache` exists but `surfsense-zero-init` does not.
# That signals an install that predates the migrations-service fix; the old
# replica may be half-initialized and would block zero-cache on next start.
test_stale_zero_cache_volume() {
    local has_zc has_zi
    has_zc=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -Fx 'surfsense-zero-cache' || true)
    has_zi=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -Fx 'surfsense-zero-init' || true)
    [[ -n "$has_zc" && -z "$has_zi" ]]
}

invoke_stale_zero_cache_cleanup() {
    if ! test_stale_zero_cache_volume; then
        return 0
    fi
    warn "Detected pre-existing 'surfsense-zero-cache' volume from an install that"
    warn "predates the migrations-service fix. It may contain a half-initialized"
    warn "SQLite replica that would block zero-cache from starting."
    warn "The volume will be removed in 5 seconds; press Ctrl+C to cancel."
    sleep 5

    (cd "${INSTALL_DIR}" && ${DC} down --remove-orphans 2>/dev/null) || true
    docker volume rm surfsense-zero-cache 2>/dev/null || true
    success "Removed surfsense-zero-cache volume; zero-cache will re-sync on next start."
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

invoke_stale_zero_cache_cleanup

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
    success "All containers started; waiting for stack to become healthy..."

    if ! wait_stack_healthy 300; then
        stack_failure_report
    fi
    success "All services healthy."

    # Key file is no longer needed — SECRET_KEY is now in .env
    rm -f "${KEY_FILE}"

else
    step "Starting SurfSense"
    (cd "${INSTALL_DIR}" && ${DC} up -d) < /dev/null
    success "All containers started; waiting for stack to become healthy..."

    if ! wait_stack_healthy 300; then
        stack_failure_report
    fi
    success "All services healthy."
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
