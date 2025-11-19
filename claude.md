# SurfSense Project Context

This file provides context for Claude Code sessions. It does NOT contain any secrets or sensitive information.

## Project Overview

SurfSense is a personal AI assistant that indexes and searches personal data from various sources (browser history, documents, connectors). It uses a multi-LLM architecture with local models for privacy and cloud fallbacks.

## Architecture

### Backend (FastAPI + Python)
- **Location**: `surfsense_backend/`
- **Database**: PostgreSQL with pgvector for embeddings
- **Task Queue**: Celery with Redis
- **Auth**: FastAPI-Users with JWT (local auth or Google OAuth)

### Frontend (Next.js)
- **Location**: `surfsense_web/`
- **Framework**: Next.js 15 with App Router
- **Styling**: Tailwind CSS
- **i18n**: next-intl (English, Latvian)

### Services on VPS
- `surfsense.service` - Backend API (port 8000)
- `surfsense-frontend.service` - Next.js (port 3000)
- `surfsense-celery.service` - Task worker
- `surfsense-celery-beat.service` - Scheduled tasks

## Secrets Management (SOPS)

Secrets are managed using SOPS with age encryption. See `docs/SECRETS_MANAGEMENT.md` for full documentation.

### Key Files
- `surfsense_backend/secrets.enc.yaml` - Encrypted secrets (safe in Git)
- `surfsense_backend/.sops.yaml` - SOPS configuration
- `~/.config/sops/age/keys.txt` - Age private key (VPS only, never in Git)

### Secret Categories
- Database credentials
- JWT secret key
- OAuth client secrets (Google, Airtable)
- External API keys (Unstructured, LlamaCloud, LangSmith, Firecrawl)
- Celery broker URLs

### MCP Server for Secrets
```bash
cd surfsense_backend
python scripts/sops_mcp_server.py list    # List secret keys
python scripts/sops_mcp_server.py get database.url  # Get specific secret
python scripts/sops_mcp_server.py set api_keys.openai "value"  # Set secret
```

## LLM Configuration

### Three-Tier Architecture
Located in `surfsense_backend/app/config/global_llm_config.yaml`:

1. **Mistral NeMo 12B (Local)** - Primary response generation
   - Provider: Ollama
   - Model: `mistral-nemo:128k`

2. **TildeOpen 30B (Local)** - Latvian grammar checker
   - Provider: Ollama
   - Model: `tildeopen:latest`

3. **Gemini 2.0 Flash (API)** - Fallback only
   - Provider: Google
   - Model: `gemini-2.0-flash-exp`

## Database Migrations

### Current State
- Latest migration: `40_add_2fa_columns_to_user`
- Migration chain: 1 → ... → 36 → 37 → 38 → 39 → 40

### Running Migrations
```bash
cd surfsense_backend
source venv/bin/activate
alembic current          # Check current version
alembic upgrade head     # Apply all migrations
alembic downgrade -1     # Rollback one migration
```

## Deployment Workflow

### Syncing Changes to VPS
1. Push to GitHub nightly branch
2. SSH to VPS
3. `cd /opt/SurfSense && git pull origin nightly`
4. Install dependencies if needed: `pip install -e .`
5. Run migrations: `alembic upgrade head`
6. Rebuild frontend if needed: `cd surfsense_web && pnpm build`
7. Restart services: `systemctl restart surfsense surfsense-celery surfsense-frontend`

### Service Management
```bash
systemctl status surfsense           # Check backend status
systemctl restart surfsense          # Restart backend
journalctl -u surfsense -n 50        # View logs
```

## Current Features

### Connectors
- Browser history (Chrome, Firefox, etc.)
- Google Calendar & Gmail
- GitHub, Slack, Discord
- Notion, Airtable, Jira, Confluence
- RSS feeds, Mastodon
- Jellyfin, Home Assistant
- Search APIs (Tavily, Serper, SearXNG, Baidu, Linkup)

### Two-Factor Authentication
- TOTP-based 2FA with QR code setup
- Backup codes for recovery
- Database columns: `two_fa_enabled`, `totp_secret`, `backup_codes`

### Site Configuration
- Customizable branding (logo, name, description)
- Social media links
- Registration enable/disable

## Development Notes

### Branch Strategy
- `main` - Stable releases
- `nightly` - Active development (primary working branch)

### Testing
```bash
cd surfsense_backend
pytest tests/
```

### Common Issues

**Migration errors**: Check revision chain in `alembic/versions/`. Revisions should use simple numbers (36, 37, 38) not full filenames.

**Backend won't start**: Check `journalctl -u surfsense -n 100` for errors. Common issues:
- Missing Python packages
- Database column mismatches
- SOPS decryption failures

**Frontend build errors**: Usually related to environment variables or TypeScript types.

## Environment Variables

See `surfsense_backend/.env.example` for all available options. Key categories:
- Database connection
- Celery configuration
- Authentication settings
- LLM/embedding models
- ETL service selection
- TTS/STT configuration

## Useful Commands

```bash
# Backend
cd surfsense_backend && source venv/bin/activate
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd surfsense_web
pnpm dev      # Development
pnpm build    # Production build

# Celery
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

## Files NOT to Commit

These are in `.gitignore`:
- `.env` files (use `.env.example` as template)
- `secrets.yaml` (unencrypted secrets)
- `keys.txt` (age private keys)
- `global_llm_config.yaml` (contains API keys)
- `uploads/` directory
- Python cache (`__pycache__`, `.pyc`)

## Recent Changes (November 2025)

1. **SOPS Integration** - Encrypted secrets management
2. **2FA Support** - Two-factor authentication for users
3. **New Connectors** - RSS, Mastodon, Jellyfin, Home Assistant
4. **Migration Fixes** - Standardized revision identifiers
5. **Security Audit** - Various security improvements

---

*Last updated: November 19, 2025*
