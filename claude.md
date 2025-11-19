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
- `surfsense-celery.service` - Task worker (background document processing)
- `surfsense-celery-beat.service` - Scheduled tasks

### VPS Server Configuration
**Server**: 30 GiB RAM, no GPU

**Memory Setup**:
- 8 GiB swap file at `/swapfile` (required for TildeOpen 30B model)
- Celery workers: ~18 workers using ~700 MB each

**Swap file setup** (already configured):
```bash
fallocate -l 8G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

**Model memory requirements**:
- `mistral-nemo:latest` (8k context): ~7 GiB
- `mistral-nemo:128k` (128k context): ~26 GiB (too large for this server)
- `tildeopen:latest`: ~21 GiB (uses swap when needed)

**Grammar check optimization** in `app/services/grammar_check.py`:
- Uses `num_ctx: 2048` to reduce memory for short grammar checks

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

1. **Gemini 2.0 Flash (API)** - Primary response generation
   - Provider: Google
   - Model: `gemini-2.0-flash-exp`
   - Fast, large context (1M+ tokens), multilingual

2. **Mistral NeMo 12B (Local)** - Fallback when Gemini fails
   - Provider: Ollama
   - Model: `mistral-nemo:latest` (8k context)
   - Slow on CPU but works offline

3. **TildeOpen 30B (Local)** - Latvian grammar checker
   - Provider: Ollama
   - Model: `tildeopen:latest`
   - Separate from main LLM flow

### Automatic Fallback System
The LLM service (`app/services/llm_service.py`) includes automatic fallback:
- **Gemini → Mistral**: If Gemini API fails (rate limits, errors), falls back to local Mistral
- Handles: connection errors, timeouts, rate limits (429), server errors (500/503)
- Transparent to the user - no manual intervention needed
- Logs warnings when fallback is used

## Database & Search Optimization

### Reranking (Enabled)
Reranking improves search quality by scoring retrieved documents by relevance:
- **Model**: `ms-marco-MiniLM-L-12-v2` (FlashRank)
- **How it works**: After vector search retrieves candidates, reranker scores them by actual query relevance
- **Benefits**: Better answer quality, fewer irrelevant documents sent to LLM

### Vector Search
- **Index type**: HNSW (Hierarchical Navigable Small World) - fast approximate nearest neighbor
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2`

### Database Statistics
- Check chunk count: `SELECT COUNT(*) FROM chunks;`
- Check document count: `SELECT COUNT(*) FROM documents;`
- View indexes (in psql): `\di+ *vector*`

### Maintenance
Run periodically for optimal performance:
```sql
VACUUM ANALYZE chunks;
VACUUM ANALYZE documents;
```

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
6. **Memory Optimization** - Switched from `mistral-nemo:128k` to `mistral-nemo:latest` (8k context) to fit in 30 GiB RAM
7. **Swap File** - Added 8 GiB swap to support TildeOpen grammar checking
8. **Grammar Check Optimization** - Reduced context window to 2048 tokens for lighter memory usage
9. **Automatic LLM Fallback** - Bidirectional fallback between Gemini (primary) and Mistral (backup)
10. **Gemini as Primary** - Switched to Gemini Flash as main LLM for speed and large context support
11. **Reranking Enabled** - FlashRank reranker for better document relevance scoring

---

*Last updated: November 19, 2025*
