#!/bin/bash
SERVER="root@46.62.230.195"
REMOTE_DIR="/opt/SurfSense/surfsense_backend"
LOCAL_DIR="$HOME/Documents/Kods/SurfSense/surfsense_backend"

echo "Syncing backend files from production..."
rsync -avz --progress \
  --exclude='.env' \
  --exclude='*.env.local' \
  --exclude='*.env.production' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache/' \
  --exclude='venv/' \
  --exclude='.venv/' \
  --exclude='*.log' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.pem' \
  --exclude='*.key' \
  --exclude='*.crt' \
  --exclude='.DS_Store' \
  -e "ssh -i ~/.ssh/id_ed25519_surfsense" \
  "$SERVER:$REMOTE_DIR/" "$LOCAL_DIR/"

echo "Sync complete!"
