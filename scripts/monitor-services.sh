#!/bin/bash
CONFIG_FILE="$(dirname "$0")/.config"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Configuration file not found at $CONFIG_FILE"
    echo "Please create it from .config.template and set your deployment variables:"
    echo "  cp $(dirname "$0")/.config.template $CONFIG_FILE"
    echo "  # Then edit $CONFIG_FILE with your actual values"
    exit 1
fi
source "$CONFIG_FILE"
VPS_KEY="${VPS_KEY/#\~/$HOME}"
ssh -i "$VPS_KEY" "$VPS_HOST" "systemctl status surfsense surfsense-celery surfsense-frontend"
