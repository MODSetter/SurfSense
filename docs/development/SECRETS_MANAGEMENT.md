# SurfSense Secrets Management with SOPS

This document describes how SurfSense manages secrets using SOPS (Secrets OPerationS) with age encryption.

## Overview

SurfSense uses SOPS to encrypt sensitive configuration values, allowing secrets to be safely stored in Git repositories while maintaining the ability to decrypt them at runtime on authorized systems.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repository                        │
│  ┌─────────────────────┐  ┌────────────────────────┐   │
│  │ secrets.enc.yaml    │  │ .sops.yaml              │   │
│  │ (encrypted secrets) │  │ (encryption config)     │   │
│  └─────────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    VPS / Local Dev                       │
│  ┌─────────────────────┐                                │
│  │ ~/.config/sops/age/ │  (age private key - NOT in Git)│
│  │ keys.txt            │                                │
│  └─────────────────────┘                                │
│              │                                          │
│              ▼                                          │
│  ┌─────────────────────┐  ┌────────────────────────┐   │
│  │ secrets_loader.py   │→ │ Environment Variables   │   │
│  │ (runtime decryption)│  │ (injected at startup)   │   │
│  └─────────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Encrypted Secrets File (`secrets.enc.yaml`)

Contains all sensitive values encrypted with age. Safe to commit to Git.

**Structure:**
```yaml
database:
  url: <encrypted>
app:
  secret_key: <encrypted>
oauth:
  google:
    client_id: <encrypted>
    client_secret: <encrypted>
  airtable:
    client_id: <encrypted>
    client_secret: <encrypted>
api_keys:
  firecrawl: <encrypted>
  unstructured: <encrypted>
  llama_cloud: <encrypted>
  langsmith: <encrypted>
services:
  celery:
    broker_url: <encrypted>
    result_backend: <encrypted>
  tts_api_key: <encrypted>
  stt_api_key: <encrypted>
```

### 2. SOPS Configuration (`.sops.yaml`)

Defines encryption rules and public keys for SOPS.

```yaml
creation_rules:
  - path_regex: secrets\.yaml$
    age: age1pa3pqtg5kxzzdukzlz6emtpem60dc79npgwh975mynn0v604cs9qefwms7
  - path_regex: secrets\.enc\.yaml$
    age: age1pa3pqtg5kxzzdukzlz6emtpem60dc79npgwh975mynn0v604cs9qefwms7
```

### 3. Age Private Key (`~/.config/sops/age/keys.txt`)

**CRITICAL: Never commit this file to Git!**

This file contains the private key needed to decrypt secrets. It must be:
- Present on production VPS
- Present on developer machines that need to decrypt
- Backed up securely (see Key Backup section)

### 4. Secrets Loader (`app/config/secrets_loader.py`)

Python module that:
- Decrypts secrets at application startup
- Injects decrypted values into environment variables
- Falls back to `.env` file if decryption fails

## Installation

### Prerequisites

1. **Install SOPS:**
   ```bash
   # On Debian/Ubuntu
   wget -qO /usr/local/bin/sops https://github.com/getsops/sops/releases/download/v3.9.1/sops-v3.9.1.linux.amd64
   chmod +x /usr/local/bin/sops

   # On macOS
   brew install sops
   ```

2. **Install age:**
   ```bash
   # On Debian/Ubuntu
   apt-get install age

   # On macOS
   brew install age
   ```

### Initial Setup (New Deployment)

1. **Generate age key pair:**
   ```bash
   mkdir -p ~/.config/sops/age
   age-keygen -o ~/.config/sops/age/keys.txt
   ```

2. **Note the public key** (shown during generation):
   ```
   Public key: age1xxxxx...
   ```

3. **Update `.sops.yaml`** with your public key.

4. **Create initial secrets file** (`secrets.yaml`):
   ```yaml
   database:
     url: postgresql+asyncpg://user:pass@host:5432/db
   app:
     secret_key: your-jwt-secret-key
   oauth:
     google:
       client_id: "your-client-id"
       client_secret: "your-secret"
   # ... etc
   ```

5. **Encrypt the secrets:**
   ```bash
   cd surfsense_backend
   sops --encrypt secrets.yaml > secrets.enc.yaml
   rm secrets.yaml  # Remove plaintext file!
   ```

6. **Commit encrypted file:**
   ```bash
   git add secrets.enc.yaml .sops.yaml
   git commit -m "Add encrypted secrets"
   ```

## Daily Operations

### Viewing Secrets

```bash
# View all secrets (decrypted)
cd surfsense_backend
sops --decrypt secrets.enc.yaml

# View specific secret using MCP server
python scripts/sops_mcp_server.py get database.url
```

### Editing Secrets

```bash
# Edit secrets in-place (opens in $EDITOR)
sops secrets.enc.yaml

# Or use the MCP server
python scripts/sops_mcp_server.py set api_keys.openai "sk-your-new-key"
```

### Adding New Secrets

1. Open encrypted file for editing:
   ```bash
   sops secrets.enc.yaml
   ```

2. Add new secret under appropriate category:
   ```yaml
   api_keys:
     openai: "sk-your-new-key"
   ```

3. Save and close. SOPS automatically re-encrypts.

4. Update `secrets_loader.py` mapping if needed.

### Deleting Secrets

```bash
# Using MCP server
python scripts/sops_mcp_server.py delete api_keys.unused_key

# Or edit directly
sops secrets.enc.yaml
# Remove the key, save, and close
```

## Key Management

### Backing Up Private Keys

**CRITICAL: Loss of private key = loss of all encrypted secrets**

1. **Export key:**
   ```bash
   cat ~/.config/sops/age/keys.txt
   ```

2. **Store securely:**
   - Password manager (1Password, Bitwarden)
   - Encrypted USB drive in safe location
   - Hardware security module (enterprise)

3. **Never:**
   - Email the key
   - Store in Git
   - Store in unencrypted cloud storage

### Key Rotation

When a key may be compromised:

1. **Generate new key pair:**
   ```bash
   age-keygen -o ~/.config/sops/age/keys-new.txt
   ```

2. **Update `.sops.yaml`** with new public key.

3. **Re-encrypt secrets:**
   ```bash
   sops updatekeys secrets.enc.yaml
   ```

4. **Distribute new private key** to all authorized systems.

5. **Remove old key** after verification.

### Adding Multiple Recipients

For team access, add multiple public keys:

```yaml
# .sops.yaml
creation_rules:
  - path_regex: secrets\.yaml$
    age: >-
      age1pa3pqtg5kxzzdukzlz6emtpem60dc79npgwh975mynn0v604cs9qefwms7,
      age1another_team_member_public_key,
      age1ci_cd_system_public_key
```

## Deployment Integration

### Docker Deployment

Mount the age key file into the container:

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - /root/.config/sops/age/keys.txt:/root/.config/sops/age/keys.txt:ro
```

### CI/CD Deployment

1. Store age private key as CI/CD secret.
2. Create key file during deployment:
   ```bash
   mkdir -p ~/.config/sops/age
   echo "$AGE_PRIVATE_KEY" > ~/.config/sops/age/keys.txt
   chmod 600 ~/.config/sops/age/keys.txt
   ```

### Manual Deployment

Copy the key file to the server:
```bash
scp ~/.config/sops/age/keys.txt user@server:~/.config/sops/age/
```

## Claude Code Integration

### MCP Server Setup

The SOPS MCP server allows Claude Code to securely manage secrets.

1. **Start the MCP server** (when needed):
   ```bash
   python scripts/sops_mcp_server.py
   ```

2. **Available commands:**
   - `sops_list_secrets` - List all secret keys
   - `sops_get_secret` - Get a specific secret
   - `sops_set_secret` - Update a secret
   - `sops_delete_secret` - Remove a secret
   - `sops_rotate_keys` - Rotate encryption
   - `sops_export_env` - Export as .env format

### CLI Usage

```bash
# List all secrets
python scripts/sops_mcp_server.py list

# Get specific secret
python scripts/sops_mcp_server.py get database.url

# Set a secret
python scripts/sops_mcp_server.py set api_keys.openai "sk-xxx"

# Export as environment variables
python scripts/sops_mcp_server.py export
```

## Security Best Practices

### DO:
- Keep age private keys in `~/.config/sops/age/keys.txt`
- Set restrictive permissions: `chmod 600 keys.txt`
- Back up private keys securely
- Rotate keys periodically (quarterly recommended)
- Use separate keys for production/staging
- Audit secret access in logs

### DON'T:
- Commit `secrets.yaml` (unencrypted)
- Commit `keys.txt` (private key)
- Store private keys in environment variables
- Share private keys via unencrypted channels
- Log decrypted secret values

### Gitignore Configuration

```gitignore
# SOPS secrets management
secrets.yaml
**/secrets.yaml
keys.txt
**/keys.txt
```

## Troubleshooting

### "SOPS binary not found"

Install SOPS:
```bash
wget -qO /usr/local/bin/sops https://github.com/getsops/sops/releases/download/v3.9.1/sops-v3.9.1.linux.amd64
chmod +x /usr/local/bin/sops
```

### "Age key file not found"

Create the key directory and file:
```bash
mkdir -p ~/.config/sops/age
# Then copy your private key or generate new one
```

### "Decryption failed"

1. Check key file exists: `ls -la ~/.config/sops/age/keys.txt`
2. Verify key matches public key in `.sops.yaml`
3. Check file permissions: `chmod 600 ~/.config/sops/age/keys.txt`

### "Application won't start after adding secrets"

1. Check secrets loader logs for errors
2. Verify YAML syntax: `sops --decrypt secrets.enc.yaml | python -c "import yaml, sys; yaml.safe_load(sys.stdin)"`
3. Ensure all required secrets are present

## Migration from .env Files

To migrate existing `.env` secrets to SOPS:

1. **Create secrets.yaml** with values from `.env`
2. **Encrypt:** `sops --encrypt secrets.yaml > secrets.enc.yaml`
3. **Update mapping** in `secrets_loader.py` if needed
4. **Test:** Restart application, verify functionality
5. **Remove sensitive values** from `.env` (keep non-sensitive config)
6. **Delete plaintext:** `rm secrets.yaml`

## Appendix: Secret Categories

### Database
- `database.url` - PostgreSQL connection string

### Application
- `app.secret_key` - JWT signing key

### OAuth Providers
- `oauth.google.client_id` / `client_secret`
- `oauth.airtable.client_id` / `client_secret`

### External APIs
- `api_keys.firecrawl`
- `api_keys.unstructured`
- `api_keys.llama_cloud`
- `api_keys.langsmith`
- `api_keys.openai` (optional)
- `api_keys.anthropic` (optional)

### Services
- `services.celery.broker_url`
- `services.celery.result_backend`
- `services.tts_api_key`
- `services.stt_api_key`
