#!/bin/bash
set -e
if [ -f "$(dirname "$0")/.config" ]; then source "$(dirname "$0")/.config"; else
VPS_HOST="root@46.62.230.195"; VPS_KEY="~/.ssh/id_ed25519_surfsense";
PROJECT_DIR="/opt/SurfSense"; fi
VPS_KEY="${VPS_KEY/#\~/$HOME}"
run_vps_cmd() { ssh -i "$VPS_KEY" "$VPS_HOST" "$1"; }
echo "🚀 Deploying..."
run_vps_cmd "cd $PROJECT_DIR && git pull origin nightly && systemctl restart surfsense surfsense-celery surfsense-frontend"
echo "✅ Deployment complete!"
