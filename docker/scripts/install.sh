#!/usr/bin/env bash
# =============================================================================
# SurfSense — One-line Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
# =============================================================================

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/MODSetter/SurfSense/main"
INSTALL_DIR="./surfsense"
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${CYAN}[SurfSense]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[SurfSense]${NC} %s\n" "$1"; }
error() { printf "${RED}[SurfSense]${NC} %s\n" "$1" >&2; exit 1; }

# ── Pre-flight checks ───────────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || error "Docker is not installed. Please install Docker first: https://docs.docker.com/get-docker/"

# Detect legacy all-in-one volume — must migrate before installing
if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q '^surfsense-data$'; then
    printf "${RED}[SurfSense]${NC} Legacy volume 'surfsense-data' detected.\n" >&2
    printf "${YELLOW}[SurfSense]${NC} You appear to be upgrading from the old all-in-one SurfSense container.\n" >&2
    printf "${YELLOW}[SurfSense]${NC} The database has been upgraded from PostgreSQL 14 to 17 and your data\n" >&2
    printf "${YELLOW}[SurfSense]${NC} must be migrated before running the new stack.\n" >&2
    printf "\n" >&2
    printf "${YELLOW}[SurfSense]${NC} Run the migration script first:\n" >&2
    printf "${CYAN}[SurfSense]${NC}   curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/migrate-database.sh | bash\n" >&2
    printf "\n" >&2
    printf "${YELLOW}[SurfSense]${NC} See the full guide at: https://surfsense.net/docs/how-to/migrate-from-allinone\n" >&2
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    error "Docker Compose is not installed. Please install Docker Compose: https://docs.docker.com/compose/install/"
fi

# ── Download files ───────────────────────────────────────────────────────────

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
    curl -fsSL "${REPO_RAW}/${src}" -o "${INSTALL_DIR}/${dest}" || error "Failed to download ${src}"
done

chmod +x "${INSTALL_DIR}/scripts/init-electric-user.sh"

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
printf "         Your personal AI-powered search engine  ${YELLOW}v${SURFSENSE_VERSION:-latest}${NC}\n"
printf "${CYAN}══════════════════════════════════════════════════════════════${NC}\n\n"
info "  Frontend:  http://localhost:3000"
info "  Backend:   http://localhost:8000"
info "  API Docs:  http://localhost:8000/docs"
info ""
info "  Config:    ${INSTALL_DIR}/.env"
info "  Logs:      cd ${INSTALL_DIR} && ${DC} logs -f"
info "  Stop:      cd ${INSTALL_DIR} && ${DC} down"
info "  Update:    cd ${INSTALL_DIR} && ${DC} pull && ${DC} up -d"
info ""
warn "  First startup may take sometime."
warn "  Edit .env to configure OAuth connectors, API keys, etc."
