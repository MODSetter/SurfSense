#!/usr/bin/env bash
# SurfSense in Docker: installs it, and updates it when run again (docs/architecture/docker.md).
#
#   curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
#
# The install lives in ./surfsense: docker-compose.yml, which each run replaces,
# and .env, which only the first run writes.

set -euo pipefail

# Wrapped, so a download cut short runs nothing.
main() {

# A test points this at a local copy of the repository.
SOURCE="${SURFSENSE_INSTALL_SOURCE:-https://raw.githubusercontent.com/MODSetter/SurfSense/main}"
PROJECT="surfsense"
# Another project's containers in "surfsense" are none of this install's business.
export COMPOSE_IGNORE_ORPHANS=1

# The app's dark palette (frontend-workflow's color/PALETTE.css), since a terminal is
# usually dark; success is green-500. 256-colour stand-ins without 24-bit colour.
paint() {
    case "${COLORTERM:-}" in
        truecolor|24bit) printf '\033[38;2;%d;%d;%dm' "$1" "$2" "$3" ;;
        *) printf '\033[38;5;%dm' "$4" ;;
    esac
}
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    PRIMARY=$(paint 217 170 144 180)      # primary #d9aa90
    FOREGROUND=$(paint 232 227 218 254)   # foreground #e8e3da
    MUTED=$(paint 142 138 131 245)        # muted-foreground #8e8a83
    SUCCESS=$(paint 34 197 94 41)         # green-500 #22c55e
    WARNING=$(paint 228 160 60 179)       # warning #e4a03c
    DESTRUCTIVE=$(paint 239 68 68 203)    # destructive #ef4444
    BOLD=$'\033[1m'; RESET=$'\033[0m'
else
    PRIMARY=""; FOREGROUND=""; MUTED=""; SUCCESS=""; WARNING=""; DESTRUCTIVE=""; BOLD=""; RESET=""
fi

info()    { printf '%s[SurfSense]%s %s\n' "$MUTED" "$RESET" "$1"; }
success() { printf '%s[SurfSense] %s%s\n' "$SUCCESS" "$1" "$RESET"; }
warn()    { printf '%s[SurfSense] %s%s\n' "$WARNING" "$1" "$RESET"; }
error()   { printf '%s[SurfSense] ERROR: %s%s\n' "$DESTRUCTIVE" "$1" "$RESET" >&2; exit 1; }
step()    { printf '\n%s%s── %s%s\n' "$BOLD" "$FOREGROUND" "$1" "$RESET"; }
# The outcome, set apart: heavy rules and an emoji on a terminal, a plain step in a log.
done_step() {
    if [[ -z "$RESET" ]]; then
        printf '\n── %s\n' "$2"
        return
    fi
    local rule
    rule=$(printf '━%.0s' $(seq 1 $(( ${#2} + 10 ))))
    printf '\n%s%s%s\n   %s  %s\n%s%s\n' "$BOLD" "$SUCCESS" "$rule" "$1" "$2" "$rule" "$RESET"
}

# Docker never reads the piped script as its own input.
compose() { (cd "$INSTALL_DIR" && docker compose "$@") < /dev/null; }

# As Compose reads it: a quoted value whole, otherwise up to " #"; CRLF from a Windows editor.
env_value() {
    local value
    value=$(grep -E "^$1=" "$INSTALL_DIR/.env" 2>/dev/null | tail -n 1 | tr -d '\r' || true)
    value="${value#*=}"
    case "$value" in
        \"*\"*) value="${value#\"}"; value="${value%%\"*}" ;;
        \'*\'*) value="${value#\'}"; value="${value%%\'*}" ;;
        *) value="${value%% #*}"; value="${value%"${value##*[![:space:]]}"}" ;;
    esac
    printf '%s' "$value"
}

is_this_install() { grep -qE '^  surfsense:' "$1/docker-compose.yml" 2>/dev/null; }

download() {
    curl -fsSL "$SOURCE/$1" -o "$INSTALL_DIR/$2.download" \
        || error "Couldn't download $2. Check your internet connection and try again."
    mv "$INSTALL_DIR/$2.download" "$INSTALL_DIR/$2"
}

image_id() { docker image inspect --format '{{.Id}}' "$1" 2>/dev/null < /dev/null || true; }

lan_address() {
    { hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || true; } | awk '{print $1}'
}

printf '\n%s' "$PRIMARY"
printf '%s\n' \
    '███████╗██╗   ██╗██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗' \
    '██╔════╝██║   ██║██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝' \
    '███████╗██║   ██║██████╔╝█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗' \
    '╚════██║██║   ██║██╔══██╗██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝' \
    '███████║╚██████╔╝██║  ██║██║     ███████║███████╗██║ ╚████║███████║███████╗' \
    '╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝'
printf '%s' "$RESET"

step "Checking prerequisites"
command -v docker > /dev/null 2>&1 \
    || error "Docker is not installed. Install it: https://docs.docker.com/get-docker/"
docker info > /dev/null 2>&1 < /dev/null \
    || error "Docker is not running. Start it and try again."
success "Docker is running."
docker compose version > /dev/null 2>&1 < /dev/null \
    || error "Docker Compose is not installed. Install it: https://docs.docker.com/compose/install/"
success "Docker Compose found."
ARCH=$(docker info --format '{{.Architecture}}' 2>/dev/null < /dev/null || true)
case "$ARCH" in
    x86_64|amd64) ;;
    *) error "SurfSense runs on x86-64 (amd64) servers only, for now. This one is ${ARCH:-unknown}." ;;
esac

# Run again from any folder, it finds the install by its container.
FOUND=$(docker ps -a \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=surfsense" \
    --format '{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null < /dev/null | head -n 1 || true)

if [[ -n "$FOUND" ]] && is_this_install "$FOUND"; then
    INSTALL_DIR="$FOUND"
elif [[ -e "$PWD/surfsense" ]]; then
    INSTALL_DIR="$PWD/surfsense"
    if ! is_this_install "$INSTALL_DIR" && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
        error "./surfsense already holds something else. Move it, or run this command from another folder."
    fi
else
    INSTALL_DIR="$PWD/surfsense"
fi

if [[ -f "$INSTALL_DIR/.env" ]]; then
    UPDATING=true
    step "Updating SurfSense in $INSTALL_DIR"
    info "Keeping your settings (.env)."
else
    UPDATING=false
    step "Downloading SurfSense"
    info "Installing into $INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
download docker/surfsense/docker-compose.yml docker-compose.yml
download docker/surfsense/.env.example .env.example
if ! $UPDATING; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    success "Created $INSTALL_DIR/.env"
fi

IMAGE=$(compose config --images 2>/dev/null | head -n 1 || true)
[[ -n "$IMAGE" ]] || error "docker-compose.yml names no image. Check $INSTALL_DIR/.env."
BEFORE=$(image_id "$IMAGE")

if [[ -z "$BEFORE" ]]; then
    step "Pulling SurfSense (about 5 GB the first time)"
else
    step "Pulling SurfSense"
fi
compose pull || error "Couldn't download the SurfSense image. Check your internet connection and try again."
AFTER=$(image_id "$IMAGE")

step "Starting SurfSense"
info "Waiting for SurfSense to be ready. A first start takes a minute or two."
if ! compose up -d --wait --wait-timeout 600; then
    compose logs --tail=40 surfsense || true
    error "SurfSense didn't start. Logs: cd $INSTALL_DIR && docker compose logs"
fi

if [[ -n "$BEFORE" && "$BEFORE" != "$AFTER" ]]; then
    # Every version is about 5 GB; the one replaced goes.
    if docker image rm "$BEFORE" > /dev/null 2>&1 < /dev/null; then
        info "Removed the previous image."
    fi
fi

VERSION=$(compose exec -T surfsense cat /app/VERSION 2>/dev/null | tr -d '[:space:]' || true)
PINNED=$(env_value SURFSENSE_VERSION)
PORT=$(env_value SURFSENSE_PORT); PORT="${PORT:-4929}"
BIND=$(env_value SURFSENSE_BIND)
DOMAIN=$(env_value SURFSENSE_DOMAIN)

if ! $UPDATING; then
    done_step "🎉" "SurfSense ${VERSION:+$VERSION }is running"
elif [[ "$BEFORE" == "$AFTER" ]]; then
    done_step "✅" "SurfSense ${VERSION:+$VERSION }is already up to date"
else
    done_step "✨" "SurfSense updated${VERSION:+ to $VERSION}"
fi
if [[ -n "$PINNED" && "$PINNED" != "latest" ]]; then
    warn "Pinned to $PINNED by SURFSENSE_VERSION in $INSTALL_DIR/.env. Set it to latest to update."
fi

echo ""
if [[ -n "$DOMAIN" ]]; then
    echo "  Open:      https://$DOMAIN"
else
    ADDRESS=""
    [[ "$BIND" == "127.0.0.1" ]] || ADDRESS=$(lan_address)
    if [[ -n "$ADDRESS" ]]; then
        echo "  Open:      http://$ADDRESS:$PORT    (any device on this network)"
        echo "             http://localhost:$PORT    (this machine)"
    else
        echo "  Open:      http://localhost:$PORT"
    fi
fi
echo ""
if ! $UPDATING; then
    echo "  The first visit asks you to create a password."
    echo ""
fi
echo "  Settings:  $INSTALL_DIR/.env"
echo "  Logs:      cd $INSTALL_DIR && docker compose logs -f"
echo "  Stop:      cd $INSTALL_DIR && docker compose down"
echo "  Update:    run this same command again"
echo ""

}

main "$@"
