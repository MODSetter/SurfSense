#!/bin/bash
set -e
CONFIG_FILE="$(dirname "$0")/.config"
TEMPLATE_PATH="$(dirname "$0")/.config.template"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Configuration file not found at $CONFIG_FILE"
    echo "Please create it from .config.template and set your deployment variables:"
    echo "  cp $TEMPLATE_PATH $CONFIG_FILE"
    echo "  # Then edit $CONFIG_FILE with your actual values"
    exit 1
fi
source "$CONFIG_FILE"
VPS_KEY="${VPS_KEY/#\~/$HOME}"
run_vps_cmd() { ssh -i "$VPS_KEY" "$VPS_HOST" "$1"; }
echo "🚀 Deploying..."
run_vps_cmd "cd $PROJECT_DIR && git pull origin nightly && systemctl restart surfsense surfsense-celery surfsense-frontend"
echo "✅ Deployment complete!"
