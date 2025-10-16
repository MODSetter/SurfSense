#!/usr/bin/env bash
set -euo pipefail

######################################################################
# SurfSense one-click installer (Conda based)
#
# This script bootstraps the SurfSense stack by:
#   1. Creating a Conda environment with Python 3.12 (configurable)
#   2. Installing the backend in editable mode with all Python deps
#   3. Installing frontend dependencies (Next.js app + browser extension)
#
# Requirements:
#   - Miniconda/Anaconda available on PATH (`conda --version`)
#   - Node.js LTS (v18+) with npm for the frontend pieces
#
# Usage:
#   chmod +x oneclick-conda-install.sh
#   ./oneclick-conda-install.sh             # installs into env `surfsense`
#   SURFSENSE_ENV_NAME=custom ./oneclick-conda-install.sh
#   SURFSENSE_PYTHON_VERSION=3.11 ./oneclick-conda-install.sh
#
# The script is idempotent — rerunning will reuse the Conda environment
# and only reinstall missing dependencies.
######################################################################

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly FRONTEND_DIR="${PROJECT_ROOT}/surfsense_web"
readonly EXTENSION_DIR="${PROJECT_ROOT}/surfsense_browser_extension"
readonly BACKEND_DIR="${PROJECT_ROOT}/surfsense_backend"

ENV_NAME="${SURFSENSE_ENV_NAME:-surfsense}"
PYTHON_VERSION="${SURFSENSE_PYTHON_VERSION:-3.12}"

info() {
    printf "\033[1;32m[INFO]\033[0m %s\n" "$*"
}

warn() {
    printf "\033[1;33m[WARN]\033[0m %s\n" "$*" >&2
}

error() {
    printf "\033[1;31m[ERROR]\033[0m %s\n" "$*" >&2
    exit 1
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Command '$cmd' not found. Please install it and re-run."
    fi
}

conda_env_exists() {
    conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"
}

conda_run() {
    conda run --no-capture-output -n "$ENV_NAME" "$@"
}

main() {
    info "SurfSense one-click Conda installer starting…"

    require_command conda

    if ! conda_env_exists; then
        info "Creating Conda environment '$ENV_NAME' with Python ${PYTHON_VERSION}…"
        conda create -y -n "$ENV_NAME" "python=${PYTHON_VERSION}"
    else
        info "Conda environment '$ENV_NAME' already exists. Reusing it."
    fi

    info "Upgrading pip/setuptools/wheel inside '$ENV_NAME'…"
    conda_run python -m pip install --upgrade pip setuptools wheel

    info "Installing SurfSense backend dependencies…"
    if [[ ! -d "${BACKEND_DIR}" ]]; then
        error "Backend directory not found at '${BACKEND_DIR}'. Verify repository layout and adjust BACKEND_DIR."
    fi
    conda_run python -m pip install -e "${BACKEND_DIR}"

    info "Installing optional developer helpers…"
    conda_run python -m pip install "pre-commit>=3.8.0"

    if command -v npm >/dev/null 2>&1; then
        if command -v node >/dev/null 2>&1; then
            NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
            if [[ "${NODE_MAJOR}" -lt 18 ]]; then
                warn "Detected Node.js v$(node -v). Require >= v18; skipping frontend installs."
                NODE_OK=false
            else
                NODE_OK=true
            fi
        else
            warn "node not found (only npm present); skipping frontend installs."
            NODE_OK=false
        fi
        if [[ "${NODE_OK:-false}" == true ]]; then
            if [[ -d "${FRONTEND_DIR}" ]]; then
                info "Installing frontend dependencies (surfsense_web)…"
                (cd "${FRONTEND_DIR}" && npm install)
            else
                warn "Frontend directory not found at '${FRONTEND_DIR}'. Skipping web app install."
            fi
            if [[ -d "${EXTENSION_DIR}" ]]; then
                info "Installing browser extension dependencies (surfsense_browser_extension)…"
                (cd "${EXTENSION_DIR}" && npm install)
            else
                warn "Extension directory not found at '${EXTENSION_DIR}'. Skipping extension install."
            fi
        fi
    else
        warn "npm not found; skipping frontend dependency installation. Install Node.js 18+ to enable the web UI."
    fi

    info "Done! To begin using SurfSense:"
    cat <<EOF

1. Activate the Conda environment:
     conda activate ${ENV_NAME}

2. Start the backend API:
     (cd "${BACKEND_DIR}" && uvicorn app.app:app --reload)
   or refer to DEPLOYMENT_GUIDE.md for production options.

3. Start the web app (if npm was available):
     (cd ${FRONTEND_DIR} && npm run dev)

Refer to README.md for next steps and environment configuration.
EOF
}

main "$@"
