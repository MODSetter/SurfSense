#!/bin/bash
if [ -f "$(dirname "$0")/.config" ]; then source "$(dirname "$0")/.config"; else
VPS_HOST="root@46.62.230.195"; VPS_KEY="~/.ssh/id_ed25519_surfsense"; fi
VPS_KEY="${VPS_KEY/#\~/$HOME}"
ssh -i "$VPS_KEY" "$VPS_HOST" "systemctl status surfsense surfsense-celery surfsense-frontend"
