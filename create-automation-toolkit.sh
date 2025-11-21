#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 SurfSense Automation Toolkit Setup${NC}"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 0; fi

echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p .git-hooks scripts
echo -e "${GREEN}✓ Directories created${NC}"

echo -e "${YELLOW}Creating Git hooks...${NC}"
cat > .git-hooks/verify-secrets << 'EOFHOOK'
#!/bin/bash
set -e
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}🔐 Verifying secrets encryption...${NC}"

FORBIDDEN_FILES=(
  "surfsense_backend/secrets.yaml"
  "surfsense_backend/.env"
  "surfsense_backend/config/global_llm_config.yaml"
  ".config/sops/age/keys.txt"
  "surfsense_backend/keys.txt"
)

FOUND_ISSUES=0

for file in "${FORBIDDEN_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${RED}❌ ERROR: Forbidden plaintext file: $file${NC}"
        FOUND_ISSUES=1
    fi
done

if [ -f "surfsense_backend/secrets.enc.yaml" ]; then
    if ! grep -q "sops:" "surfsense_backend/secrets.enc.yaml" || ! grep -q "mac:" "surfsense_backend/secrets.enc.yaml"; then
        echo -e "${RED}❌ ERROR: secrets.enc.yaml not encrypted!${NC}"
        FOUND_ISSUES=1
    else
        echo -e "${GREEN}✓ secrets.enc.yaml is properly encrypted${NC}"
    fi
fi

if [ $FOUND_ISSUES -eq 1 ]; then
    echo -e "${RED}❌ COMMIT BLOCKED: Security issues detected!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All checks passed!${NC}"
exit 0
EOFHOOK

cat > .git-hooks/pre-commit-local << 'EOFHOOK'
#!/bin/bash
set -e
if command -v pre-commit &> /dev/null; then
    pre-commit run --hook-stage pre-commit
fi
echo "Running secrets verification..."
.git-hooks/verify-secrets
EOFHOOK

chmod +x .git-hooks/verify-secrets .git-hooks/pre-commit-local
echo -e "${GREEN}✓ Git hooks created${NC}"

echo -e "${YELLOW}Creating scripts...${NC}"
cat > scripts/deploy.sh << 'EOFSCRIPT'
#!/bin/bash
set -e

# Configuration file path
CONFIG_PATH="$(dirname "$0")/.config"

# Load configuration or exit with error
if [ -f "$CONFIG_PATH" ]; then
    source "$CONFIG_PATH"
else
    echo "ERROR: Configuration file not found: $CONFIG_PATH" >&2
    echo "Please copy scripts/.config.template to $CONFIG_PATH and configure your VPS details." >&2
    exit 1
fi

# Expand tilde in SSH key path
VPS_KEY="${VPS_KEY/#\~/$HOME}"

# Helper function to run commands on VPS
run_vps_cmd() {
    ssh -i "$VPS_KEY" "$VPS_HOST" "$1"
}

echo "🚀 Deploying..."
run_vps_cmd "cd $PROJECT_DIR && git pull origin nightly && systemctl restart surfsense surfsense-celery surfsense-frontend"
echo "✅ Deployment complete!"
EOFSCRIPT

cat > scripts/monitor-services.sh << 'EOFSCRIPT'
#!/bin/bash

# Configuration file path
CONFIG_PATH="$(dirname "$0")/.config"

# Load configuration or exit with error
if [ -f "$CONFIG_PATH" ]; then
    source "$CONFIG_PATH"
else
    echo "ERROR: Configuration file not found: $CONFIG_PATH" >&2
    echo "Please copy scripts/.config.template to $CONFIG_PATH and configure your VPS details." >&2
    exit 1
fi

# Expand tilde in SSH key path
VPS_KEY="${VPS_KEY/#\~/$HOME}"

# Monitor service status on VPS
ssh -i "$VPS_KEY" "$VPS_HOST" "systemctl status surfsense surfsense-celery surfsense-frontend"
EOFSCRIPT

cat > scripts/cleanup-secrets.sh << 'EOFSCRIPT'
#!/bin/bash
echo "🔒 Cleaning up plaintext secrets..."
rm -f surfsense_backend/secrets.yaml surfsense_backend/.env surfsense_backend/.env.backup.*
echo "✅ Done!"
EOFSCRIPT

cat > scripts/.config.template << 'EOF'
VPS_HOST="user@<your-vps-ip-address>"
VPS_KEY="~/.ssh/id_ed25519_surfsense"
PROJECT_DIR="/opt/SurfSense"
EOF

chmod +x scripts/*.sh
echo -e "${GREEN}✓ Scripts created${NC}"

if ! grep -q "scripts/.config" .gitignore 2>/dev/null; then
    echo -e "\n# Script configuration\nscripts/.config" >> .gitignore
    echo -e "${GREEN}✓ .gitignore updated${NC}"
fi

echo -e "${YELLOW}Testing hooks...${NC}"
./.git-hooks/verify-secrets || true

echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Link hook: ln -sf ../../.git-hooks/pre-commit-local .git/hooks/pre-commit"
echo "2. Clean secrets: ./scripts/cleanup-secrets.sh"
echo "3. Test commit: git add . && git commit -m 'test: verify hooks'"

