#!/usr/bin/env bash
# =============================================================================
# SurfSense — One-line Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
# =============================================================================

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/MODSetter/SurfSense/main"
INSTALL_DIR="./surfsense"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[SurfSense]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[SurfSense]${NC} %s\n" "$1"; }
error() { printf "${RED}[SurfSense]${NC} %s\n" "$1" >&2; exit 1; }

# ── Pre-flight checks ───────────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || error "Docker is not installed. Please install Docker first: https://docs.docker.com/get-docker/"

if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    error "Docker Compose is not installed. Please install Docker Compose: https://docs.docker.com/compose/install/"
fi

# ── Download files ───────────────────────────────────────────────────────────

info "Creating installation directory: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

FILES=(
    "docker/docker-compose.yml:docker-compose.yml"
    "docker/.env.example:.env.example"
    "docker/postgresql.conf:postgresql.conf"
    "docker/scripts/init-electric-user.sh:init-electric-user.sh"
)

for entry in "${FILES[@]}"; do
    src="${entry%%:*}"
    dest="${entry##*:}"
    info "Downloading ${dest}..."
    curl -fsSL "${REPO_RAW}/${src}" -o "${INSTALL_DIR}/${dest}" || error "Failed to download ${src}"
done

chmod +x "${INSTALL_DIR}/init-electric-user.sh"

# ── Set up .env ──────────────────────────────────────────────────────────────

if [ ! -f "${INSTALL_DIR}/.env" ]; then
    cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"

    SECRET_KEY=$(openssl rand -base64 32 2>/dev/null || head -c 32 /dev/urandom | base64)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${SECRET_KEY}|" "${INSTALL_DIR}/.env"
    else
        sed -i "s|SECRET_KEY=replace_me_with_a_random_string|SECRET_KEY=${SECRET_KEY}|" "${INSTALL_DIR}/.env"
    fi

    info "Generated random SECRET_KEY in .env"
else
    warn ".env already exists — skipping (your existing config is preserved)"
fi

# ── Start containers ─────────────────────────────────────────────────────────

info "Starting SurfSense..."
cd "${INSTALL_DIR}"
${DC} up -d

echo ""
info "=========================================="
info "  SurfSense is starting up!"
info "=========================================="
info ""
info "  Frontend:  http://localhost:3000"
info "  Backend:   http://localhost:8000"
info "  API Docs:  http://localhost:8000/docs"
info ""
info "  Config:    ${INSTALL_DIR}/.env"
info "  Logs:      cd ${INSTALL_DIR} && ${DC} logs -f"
info "  Stop:      cd ${INSTALL_DIR} && ${DC} down"
info "  Update:    cd ${INSTALL_DIR} && ${DC} pull && ${DC} up -d"
info ""
warn "  First startup may take a few minutes while images are pulled."
warn "  Edit .env to configure OAuth connectors, API keys, etc."
info "=========================================="
