# SurfSense Security & Architecture Audit Report

**Audit Date:** 2025-11-17
**Audited By:** Claude AI Assistant (Anthropic)
**Repository:** https://github.com/okapteinis/SurfSense
**Branch:** claude/surfsense-audit-automation-01MeVuvAybnL5NXHG5W3XuXe
**Upstream:** https://github.com/MODSetter/SurfSense
**Session Topic:** Comprehensive Security, Architecture, and Compliance Audit

---

## Executive Summary

This report documents a comprehensive security and architecture audit of the SurfSense repository. SurfSense is an AI-powered research agent and personal knowledge base system that integrates with various external sources (Slack, Linear, GitHub, Notion, etc.) and supports local/cloud LLM deployments.

**Overall Assessment:** ✅ **GOOD** with recommendations for enhancement

The codebase demonstrates strong security practices with automated tooling (detect-secrets, pre-commit hooks, bandit), modern architecture (FastAPI + Next.js), and comprehensive documentation. Several recommendations are provided to further strengthen security posture and automation capabilities.

---

## 1. Scope of Audit

### 1.1 What Was Checked

✅ **Security & Secrets Scanning**
- Scanned all source files for hardcoded credentials, API keys, tokens
- Reviewed `.env.example` files for placeholder safety
- Validated `.gitignore` coverage for sensitive files
- Analyzed pre-commit hooks and detect-secrets baseline
- Checked for exposed private keys, certificates, database credentials

✅ **Architecture & LLM/RAG Components**
- Reviewed FastAPI backend architecture
- Analyzed hybrid search implementation (vector + full-text)
- Examined LangGraph agent configurations
- Validated embedding models and reranker setup
- Assessed PostgreSQL/pgvector integration
- Reviewed Celery/Redis async task architecture

✅ **Platform Compatibility**
- Python version requirements (3.12+)
- Node.js/npm package versions
- Docker containerization setup
- Multi-platform support (x86_64, ARM)

✅ **Licensing & Copyright**
- Scanned all LICENSE files
- Checked for license headers in source files
- Verified third-party dependency licenses

✅ **Documentation Quality**
- Reviewed README.md, CONTRIBUTING.md
- Examined setup guides (Chinese LLM guide, etc.)
- Validated configuration examples

---

## 2. Security Audit Results

### 2.1 Secrets & Credentials Analysis

#### ✅ **Status: SECURE - No Real Secrets Found**

**Findings:**
1. **All API keys in codebase are placeholders:**
   - `.env.example` files use obvious placeholders:
     - `SECRET_KEY=SECRET`
     - `GOOGLE_OAUTH_CLIENT_ID=924507538m` (partial/example)
     - `FIRECRAWL_API_KEY=fcr-01J0000000000000000000000` (zeros)
     - `UNSTRUCTURED_API_KEY=Tpu3P0U8iy` (short placeholder)
     - `LLAMA_CLOUD_API_KEY=llx-nnn` (obvious placeholder)

2. **Configuration templates are safe:**
   - `surfsense_backend/app/config/global_llm_config.example.yaml` uses:
     - `sk-your-openai-api-key-here`
     - `sk-ant-your-anthropic-api-key-here`
     - `your-deepseek-api-key-here`

3. **Documentation examples use masked placeholders:**
   - `docs/chinese-llm-setup.md` uses `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

4. **No .env files committed:**
   - Only `.env.example` files present (verified with `ls -la`)
   - Real `.env` files properly gitignored

#### ✅ **Security Tooling in Place**

**Excellent automated security measures:**

1. **detect-secrets** (v1.5.0) with comprehensive detectors:
   - ✅ AWS Key Detector
   - ✅ Azure Storage Key Detector
   - ✅ GitHub Token Detector
   - ✅ JWT Token Detector
   - ✅ Private Key Detector
   - ✅ Slack Detector
   - ✅ Discord Bot Token Detector
   - ✅ High Entropy String Detectors (Base64, Hex)
   - ✅ And 15+ more detectors
   - Baseline file: `.secrets.baseline` (currently clean: `"results": {}`)

2. **Pre-commit hooks** (`.pre-commit-config.yaml`):
   - ✅ Secret detection on every commit
   - ✅ Bandit (Python security linter) - high severity checks
   - ✅ Ruff (Python linting + formatting)
   - ✅ Biome (TypeScript/JavaScript linting)
   - ✅ YAML/JSON/TOML validation
   - ✅ Large file prevention (10MB limit)
   - ✅ Commit message linting (commitizen)

### 2.2 .gitignore Analysis

#### ⚠️ **Status: MINIMAL - Needs Enhancement**

**Current .gitignore (5 entries only):**
```
.flashrank_cache*
podcasts/
.env
node_modules/
.ruff_cache/
```

**Issues:**
- ❌ Missing common Python cache patterns (`__pycache__/`, `*.pyc`, `*.pyo`)
- ❌ Missing test/coverage artifacts (`.pytest_cache/`, `.coverage`, `htmlcov/`)
- ❌ Missing build artifacts (`dist/`, `build/`, `*.egg-info/`)
- ❌ Missing environment variations (`.env.local`, `.env.production`, `.env.*.local`)
- ❌ Missing credentials/secrets patterns (`*.key`, `*.pem`, `*.cert`, `credentials.json`, `secrets.*`)
- ❌ Missing log files (`*.log`, `logs/`, `.log/`)
- ❌ Missing OS-specific files (`.DS_Store`, `Thumbs.db`)
- ❌ Missing IDE files (`.idea/`, `*.swp`, `*.swo`)
- ❌ Missing database files (`*.db`, `*.sqlite`, `*.sqlite3`)

**Recommendation:** Enhance `.gitignore` with comprehensive patterns (see Recommendations section).

### 2.3 Docker Security

#### ✅ **Status: GOOD** with minor notes

**Findings:**
1. **Multi-stage builds:** Not used, but acceptable for this project size
2. **Base image:** `python:3.12-slim` (good - minimal attack surface)
3. **Security updates:** ✅ Includes `apt-get update`, certificate management
4. **Non-root user:** ❌ Runs as root (line 75: no USER directive)
5. **Secrets handling:** ✅ Uses `.env` files, not baked into image
6. **SSL certificates:** ✅ Properly configured with certifi

**docker-compose.yml:**
- ✅ Uses environment variable substitution
- ✅ Default credentials are weak (`postgres:postgres`) but documented for local dev
- ✅ Services properly isolated with Docker networks
- ✅ pgAdmin included for database management

---

## 3. LLM/RAG Architecture Summary

### 3.1 Architecture Overview

**SurfSense implements a sophisticated 2-tier Hierarchical RAG system:**

```
┌─────────────────────────────────────────────────────────────┐
│                     USER QUERY                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              TIER 1: Document-Level Search                   │
│  • Hybrid Search (Vector + Full-Text)                       │
│  • PostgreSQL pgvector (<=> operator)                       │
│  • Reciprocal Rank Fusion (RRF)                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              TIER 2: Chunk-Level Search                      │
│  • Fine-grained retrieval within selected documents         │
│  • Vector + Full-Text Hybrid Search                         │
│  • RRF fusion for optimal ranking                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   RERANKING (Optional)                       │
│  • Cohere, FlashRank, Pinecone rerankers                    │
│  • Model: ms-marco-MiniLM-L-12-v2 (default)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              LLM RESPONSE GENERATION                         │
│  • LiteLLM (100+ LLM support)                               │
│  • LangGraph agent orchestration                            │
│  • Cited answers (Perplexity-style)                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Core Components

#### **A. Embedding Models**
- **Library:** Chonkie `AutoEmbeddings` (v1.4.0+)
- **Default:** `sentence-transformers/all-MiniLM-L6-v2` (local)
- **Supported Providers:**
  - Sentence Transformers (local, 6000+ models)
  - OpenAI (`openai://text-embedding-ada-002`)
  - Anthropic (`anthropic://claude-v1`)
  - Cohere (`cohere://embed-english-light-v3.0`)
  - Configurable via `EMBEDDING_MODEL` environment variable

#### **B. Vector Database**
- **Technology:** PostgreSQL 14+ with pgvector extension
- **Storage:** `ankane/pgvector:latest` Docker image
- **Operations:**
  - Cosine similarity: `<=>` operator
  - Efficient indexing for large-scale vector search

#### **C. Hybrid Search Implementation**

**File:** `surfsense_backend/app/retriver/documents_hybrid_search.py`
**File:** `surfsense_backend/app/retriver/chunks_hybrid_search.py`

**Features:**
1. **Vector Search:**
   - Embeddings stored in PostgreSQL vector columns
   - Cosine similarity ranking via `<=>` operator

2. **Full-Text Search:**
   - PostgreSQL `to_tsvector()` / `plainto_tsquery()`
   - English language support (configurable)

3. **Reciprocal Rank Fusion (RRF):**
   - Combines vector + full-text results
   - Optimal ranking for diverse query types

4. **Security:**
   - User-based access control (`user_id` filtering)
   - Search space isolation (`search_space_id`)

#### **D. Chunking Strategy**

- **Library:** Chonkie `LateChunker` (v1.4.0+)
- **Approach:** Adaptive chunking based on embedding model's max sequence length
- **Benefits:**
  - Prevents token overflow
  - Optimizes chunk size for embedding quality
  - Automatic adaptation to different models

#### **E. Rerankers (Optional)**

**Enabled via:** `RERANKERS_ENABLED=TRUE`

**Supported Models:**
- FlashRank (`ms-marco-MiniLM-L-12-v2`) - default
- Cohere
- Pinecone
- Others via `rerankers` library (v0.7.1+)

#### **F. LLM Integration**

**Primary Framework:** LiteLLM (v1.77.5+)

**Supported Providers (100+):**
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude Sonnet, Opus, Haiku)
- Google (Gemini, Vertex AI)
- Chinese LLMs:
  - DeepSeek
  - Alibaba Qwen (通义千问)
  - Moonshot Kimi (月之暗面)
  - Zhipu GLM (智谱 AI)
- OpenRouter
- Comet API
- Groq
- And 90+ more...

**Configuration:** `surfsense_backend/app/config/global_llm_config.example.yaml`

#### **G. Agent Framework**

**Technology:** LangGraph (v0.3.29+)

**Agents:**
1. **Researcher Agent** (`app/agents/researcher/`)
   - Multi-step research workflows
   - External source integration (Slack, GitHub, Notion, etc.)
   - Search engine connectors (Tavily, LinkUp, SearxNG)

2. **QNA Agent** (`app/agents/researcher/qna_agent/`)
   - Question-answering on saved content
   - Citation generation (Perplexity-style)

3. **Podcaster Agent** (`app/agents/podcaster/`)
   - Blazingly fast podcast generation (<20s for 3-min podcast)
   - TTS support:
     - Local: Kokoro TTS
     - Cloud: OpenAI, Azure, Google Vertex AI
   - STT support: Faster-Whisper (local), LiteLLM providers

#### **H. Document Processing (ETL)**

**Configurable via:** `ETL_SERVICE` environment variable

**Options:**
1. **Docling** (default, privacy-focused, no API key)
   - Local processing
   - Supports: PDF, DOCX, HTML, images, CSV

2. **Unstructured.io** (API-based, 34+ formats)
   - Cloud processing
   - Requires `UNSTRUCTURED_API_KEY`

3. **LlamaCloud** (API-based, 50+ formats)
   - Enhanced parsing
   - Requires `LLAMA_CLOUD_API_KEY`

#### **I. Async Task Queue**

- **Technology:** Celery (v5.5.3+) + Redis (v5.2.1+)
- **Workers:** Handle document processing, podcast generation
- **Scheduler:** Celery Beat for periodic connector syncing
- **Monitoring:** Flower (v2.0.1+) on port 5555

### 3.3 External Connectors

**Supported Integrations (15+):**
- Search Engines: Tavily, LinkUp, SearxNG, Baidu, Serper
- Collaboration: Slack, Discord
- Project Management: Linear, Jira, ClickUp, Airtable, Luma
- Documentation: Notion, Confluence
- Cloud Storage: Google Calendar, Gmail
- Development: GitHub
- Custom: Elasticsearch

---

## 4. Platform Compatibility

### 4.1 Backend (Python)

**Version:** Python 3.12+
**Package Manager:** uv + pip
**Status:** ✅ **MODERN & COMPATIBLE**

**Key Dependencies:**
- FastAPI 0.115.8+ (latest stable)
- SQLAlchemy 2.x (async support)
- Alembic 1.13.0+ (database migrations)
- LangChain/LangGraph (latest stable)
- PyTorch (CUDA 12.1 support on x86_64, CPU on ARM)

**Compatibility Notes:**
- ✅ Python 3.12 is current stable (released Oct 2023)
- ✅ All major dependencies are actively maintained
- ✅ Multi-platform Docker support (x86_64, ARM)
- ⚠️ Requires significant system resources (ML models, embeddings)

### 4.2 Frontend (Node.js/React)

**Versions:**
- Node.js: 20+ (inferred from package.json `@types/node: ^20.19.9`)
- Next.js: 15.5.6 (latest stable)
- React: 19.1.0 (latest stable, released Dec 2024)
- TypeScript: 5.8.3 (latest stable)

**Status:** ✅ **CUTTING-EDGE & MODERN**

**Build System:**
- Next.js 15 with Turbopack (ultra-fast bundler)
- Tailwind CSS 4.x (latest major version)
- Biome 2.1.2 (Rust-based linter/formatter)

**Compatibility Notes:**
- ✅ React 19 is production-ready (Dec 2024 release)
- ✅ Next.js 15 App Router (modern architecture)
- ✅ All dependencies actively maintained
- ⚠️ React 19 is very new - ensure thorough testing for SSR edge cases

### 4.3 Docker & DevOps

**Docker Compose:** v3.8
**Images:**
- Backend: Python 3.12-slim
- Database: `ankane/pgvector:latest`
- Redis: `redis:7-alpine`
- pgAdmin: `dpage/pgadmin4`

**Status:** ✅ **PRODUCTION-READY**

**Features:**
- ✅ Multi-container orchestration
- ✅ Volume persistence (postgres_data, redis_data, pgadmin_data)
- ✅ Environment variable configuration
- ✅ Health checks and dependencies
- ⚠️ No explicit resource limits (CPU/memory) - consider for production

---

## 5. Licensing & Copyright

### 5.1 Main License

**License:** Apache License 2.0
**File:** `/LICENSE` (202 lines)

**Key Terms:**
- ✅ Commercial use allowed
- ✅ Modification allowed
- ✅ Distribution allowed
- ✅ Patent grant included
- ✅ Requires attribution notice
- ✅ Requires license inclusion in distributions
- ✅ Changes must be documented

**Note:** User mentioned "CC BY-NC-ND 4.0" in instructions, but repository uses **Apache 2.0**. This is a **permissive open-source license**, not Creative Commons.

### 5.2 License Headers

**Status:** ❌ **NOT PRESENT** in source files

**Findings:**
- No license headers found in Python files
- No license headers found in TypeScript/JavaScript files
- Only top-level LICENSE files present

**Recommendation:**
While not required by Apache 2.0, adding SPDX license identifiers to source files is a best practice:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 SurfSense Contributors
```

### 5.3 Third-Party Dependencies

**Backend (Python):**
- All dependencies use permissive licenses (MIT, Apache, BSD)
- No GPL/AGPL "viral" licenses detected

**Frontend (Node.js):**
- All dependencies use permissive licenses (MIT, Apache, BSD)
- React, Next.js, Tailwind: MIT License

**Status:** ✅ **LICENSE-COMPATIBLE** - No conflicts found

### 5.4 Co-Authorship Policy

**Current Status:**
- No explicit co-authorship markers in commit history
- Standard Git commit metadata used

**Recommendation (per user instructions):**
For audit sessions and significant contributions, use Git co-author trailers:

```bash
git commit -m "Add feature X

Co-authored-by: Ojārs Kapteiņš <ojars@kapteinis.lv>
Co-authored-by: Claude AI Assistant <odede@anthropic.com>"
```

**For file-level attribution:**
```python
# Contributors:
# - Original Author: SurfSense Team
# - Security Review: Ojārs Kapteiņš <ojars@kapteinis.lv>, 2025-11-17
# - Architecture Audit: Claude AI Assistant, 2025-11-17
```

---

## 6. Documentation Review

### 6.1 Files Reviewed

✅ **README.md** (316 lines)
- Comprehensive feature list
- Installation options (Cloud, Docker, Manual)
- Tech stack documentation
- Screenshots and demos
- Star history and contribution guidelines

✅ **CONTRIBUTING.md** (exists)
- Contribution workflow documented

✅ **CODE_OF_CONDUCT.md** (exists)
- Community standards documented

✅ **docs/chinese-llm-setup.md**
- Excellent multi-language support
- Detailed setup for DeepSeek, Qwen, Moonshot, Zhipu
- Includes API key examples (all properly masked: `sk-xxx`)

### 6.2 Missing Documentation (per user instructions)

❌ **INSTALLATION_LOCAL_LLM.md** - Not found
❌ **MIGRATION_LOCAL_LLM.md** - Not found
❌ **PR_DESCRIPTION.md** - Not found

**Note:** These specific files were mentioned in audit requirements but don't exist. Equivalent documentation may exist under different names or in online docs (surfsense.net/docs).

### 6.3 Documentation Quality

**Status:** ✅ **EXCELLENT**

**Strengths:**
- Clear, well-structured README
- Multi-language support (English, Chinese)
- Comprehensive setup guides
- Code examples properly sanitized
- Active roadmap (GitHub Projects)

**Recommendations:**
- Add local LLM migration guide (if needed)
- Document disaster recovery procedures
- Add API reference documentation

---

## 7. Key Findings & Recommendations

### 7.1 Critical (Fix Immediately)

**None found.** ✅ No critical security vulnerabilities detected.

### 7.2 High Priority

1. **Enhance .gitignore**
   - **Risk:** Accidental commit of secrets/caches
   - **Action:** Add comprehensive patterns (see Appendix A)
   - **Effort:** 10 minutes

2. **Add Docker non-root user**
   - **Risk:** Container runs as root (privilege escalation if compromised)
   - **Action:** Add `USER` directive to Dockerfile
   - **Effort:** 5 minutes

### 7.3 Medium Priority

3. **Add SPDX license identifiers to source files**
   - **Risk:** License ambiguity in file extracts
   - **Action:** Add `# SPDX-License-Identifier: Apache-2.0` to files
   - **Effort:** 2 hours (automated via script)

4. **Document upstream sync automation**
   - **Risk:** Manual sync errors, stale fork
   - **Action:** Create GitHub Actions workflow (see Appendix B)
   - **Effort:** 1 hour

5. **Add resource limits to docker-compose.yml**
   - **Risk:** Resource exhaustion in production
   - **Action:** Add `deploy.resources.limits` to services
   - **Effort:** 30 minutes

### 7.4 Low Priority

6. **Strengthen default database credentials**
   - **Risk:** Production deployments with weak defaults
   - **Action:** Document strong password generation in setup guide
   - **Effort:** 15 minutes

7. **Add security.txt**
   - **Risk:** Unclear vulnerability disclosure process
   - **Action:** Create `.well-known/security.txt` (RFC 9116)
   - **Effort:** 30 minutes

8. **Enable Dependabot**
   - **Risk:** Outdated dependencies with known CVEs
   - **Action:** Add `.github/dependabot.yml`
   - **Effort:** 15 minutes

---

## 8. Compliance Checklist

### 8.1 Security Checklist

- [x] No hardcoded secrets in codebase
- [x] `.env.example` files use placeholders only
- [x] Real `.env` files gitignored
- [x] Automated secret scanning (detect-secrets)
- [x] Pre-commit hooks for security
- [x] SQL injection prevention (SQLAlchemy ORM)
- [x] XSS prevention (React auto-escaping, rehype-sanitize)
- [x] CSRF protection (FastAPI CORS, SameSite cookies)
- [x] User authentication (FastAPI Users, OAuth)
- [x] Database access control (user_id filtering)
- [ ] Docker non-root user (RECOMMENDED)
- [x] SSL/TLS certificate management
- [ ] Comprehensive .gitignore (NEEDS IMPROVEMENT)

### 8.2 Code Quality Checklist

- [x] Python linting (Ruff)
- [x] Python security scanning (Bandit)
- [x] TypeScript linting (Biome)
- [x] Pre-commit hooks enabled
- [x] Commit message linting (commitizen)
- [x] Type safety (TypeScript, Python type hints)
- [x] Database migrations (Alembic)
- [x] API versioning (/api/v1/)

### 8.3 Documentation Checklist

- [x] README with installation instructions
- [x] Contributing guidelines
- [x] Code of conduct
- [x] License file (Apache 2.0)
- [x] Setup guides for major features
- [ ] API reference documentation (RECOMMENDED)
- [ ] Disaster recovery guide (RECOMMENDED)
- [ ] Local LLM migration guide (per user requirements)

### 8.4 DevOps Checklist

- [x] Docker containerization
- [x] Docker Compose orchestration
- [x] Environment variable configuration
- [x] Database persistence (volumes)
- [x] Health checks (implicit in dependencies)
- [ ] Resource limits (RECOMMENDED)
- [ ] GitHub Actions CI/CD (RECOMMENDED)
- [ ] Automated dependency updates (RECOMMENDED)
- [ ] Automated upstream sync (per user requirements)

---

## 9. Upstream Sync Automation

### 9.1 Current Sync Status

**Fork:** okapteinis/SurfSense
**Upstream:** MODSetter/SurfSense
**Branch Strategy:**
- `main` - stable releases, synced with upstream
- `nightly` - development branch for testing
- `claude/*` - audit/feature branches

### 9.2 Recommended Sync Workflow

**Per user instructions:**

```bash
# Step 1: Add upstream remote (one-time)
git remote add upstream https://github.com/MODSetter/SurfSense
git remote -v  # Verify

# Step 2: Fetch upstream changes
git fetch upstream

# Step 3: Sync main branch
git checkout main
git merge upstream/main --no-edit
git push origin main

# Step 4: Sync nightly from main (after audit)
git checkout nightly
git merge main --no-edit
git push origin nightly
```

### 9.3 Automated Sync (GitHub Actions)

**See Appendix B** for complete GitHub Actions workflow.

**Schedule:** Daily at 00:00 UTC
**Trigger:** Manual dispatch available
**Safety:** Creates PR instead of direct push (requires approval)

---

## 10. TODOs for Future Maintainers

### 10.1 Immediate Actions

- [ ] Review and apply .gitignore enhancements (Appendix A)
- [ ] Add non-root Docker user to Dockerfile
- [ ] Document upstream sync workflow in CONTRIBUTING.md
- [ ] Create GitHub Actions workflow for automated sync (Appendix B)

### 10.2 Short-Term (1-2 weeks)

- [ ] Add SPDX license identifiers to source files (script in Appendix C)
- [ ] Enable Dependabot for automated dependency updates
- [ ] Add resource limits to docker-compose.yml for production
- [ ] Create API reference documentation (OpenAPI/Swagger)
- [ ] Document disaster recovery procedures

### 10.3 Long-Term (1-3 months)

- [ ] Set up GitHub Actions CI/CD pipeline
- [ ] Add end-to-end testing with Playwright
- [ ] Create security.txt for vulnerability disclosure
- [ ] Implement monitoring/observability (OpenTelemetry)
- [ ] Add load testing for production readiness
- [ ] Create migration guides for major version upgrades

---

## Appendices

### Appendix A: Enhanced .gitignore

```gitignore
# SurfSense - Comprehensive .gitignore
# Generated by Claude Code Audit (2025-11-17)

# ============================================================================
# SECRETS & CREDENTIALS (CRITICAL)
# ============================================================================
.env
.env.local
.env.*.local
.env.production
.env.development
.env.staging

# API Keys & Credentials
*.key
*.pem
*.cert
*.crt
*.p12
*.pfx
credentials.json
secrets.*
secret.*
auth.json
service-account*.json

# ============================================================================
# PYTHON
# ============================================================================
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environments
venv/
ENV/
env/
.venv

# Testing & Coverage
.pytest_cache/
.coverage
.coverage.*
htmlcov/
.tox/
.nox/
.hypothesis/
nosetests.xml
coverage.xml
*.cover
.cache

# Jupyter Notebook
.ipynb_checkpoints

# Ruff
.ruff_cache/

# MyPy
.mypy_cache/
.dmypy.json
dmypy.json

# Pytype
.pytype/

# ============================================================================
# NODE.JS / JAVASCRIPT / TYPESCRIPT
# ============================================================================
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.yarn-integrity
.pnpm-debug.log*

# Next.js
.next/
out/
.turbo/

# Build outputs
dist/
build/
*.tsbuildinfo

# Testing
coverage/

# ============================================================================
# DATABASES
# ============================================================================
*.db
*.sqlite
*.sqlite3
*.db-shm
*.db-wal

# PostgreSQL
*.dump
*.backup

# ============================================================================
# LOGS
# ============================================================================
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*
.pnpm-debug.log*

# ============================================================================
# OS SPECIFIC
# ============================================================================
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
Desktop.ini

# ============================================================================
# IDE / EDITOR
# ============================================================================
.vscode/
.idea/
*.swp
*.swo
*~
*.bak
*.tmp

# ============================================================================
# PROJECT SPECIFIC
# ============================================================================
# Cache directories
.flashrank_cache*
.ruff_cache/

# Generated content
podcasts/

# Temporary files
temp/
tmp/
*.tmp

# Docker volumes (if using local bind mounts)
postgres_data/
redis_data/
pgadmin_data/

# ============================================================================
# MISC
# ============================================================================
.pytest_cache/
.mypy_cache/
.dmypy.json
.pyre/
celerybeat-schedule
celerybeat.pid
```

### Appendix B: GitHub Actions Upstream Sync Workflow

Create `.github/workflows/sync-upstream.yml`:

```yaml
name: Sync Fork with Upstream

on:
  schedule:
    # Run daily at 00:00 UTC
    - cron: '0 0 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Fetch all history
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Configure Git
        run: |
          git config user.name "GitHub Actions Bot"
          git config user.email "actions@github.com"

      - name: Add upstream remote
        run: |
          git remote add upstream https://github.com/MODSetter/SurfSense.git || true
          git remote -v

      - name: Fetch upstream changes
        run: |
          git fetch upstream
          git fetch origin

      - name: Check for upstream changes
        id: check
        run: |
          UPSTREAM_SHA=$(git rev-parse upstream/main)
          ORIGIN_SHA=$(git rev-parse origin/main)
          if [ "$UPSTREAM_SHA" != "$ORIGIN_SHA" ]; then
            echo "changes=true" >> $GITHUB_OUTPUT
            echo "Upstream has new commits"
          else
            echo "changes=false" >> $GITHUB_OUTPUT
            echo "No upstream changes"
          fi

      - name: Create sync branch
        if: steps.check.outputs.changes == 'true'
        run: |
          BRANCH_NAME="sync/upstream-$(date +%Y%m%d-%H%M%S)"
          git checkout -b $BRANCH_NAME origin/main
          echo "BRANCH_NAME=$BRANCH_NAME" >> $GITHUB_ENV

      - name: Merge upstream changes
        if: steps.check.outputs.changes == 'true'
        run: |
          git merge upstream/main --no-edit || {
            echo "Merge conflict detected. Manual intervention required."
            exit 1
          }

      - name: Push sync branch
        if: steps.check.outputs.changes == 'true'
        run: |
          git push origin $BRANCH_NAME

      - name: Create Pull Request
        if: steps.check.outputs.changes == 'true'
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          branch: ${{ env.BRANCH_NAME }}
          base: main
          title: "🔄 Sync with upstream MODSetter/SurfSense"
          body: |
            ## Automated Upstream Sync

            This PR syncs the fork with the latest changes from [MODSetter/SurfSense](https://github.com/MODSetter/SurfSense).

            **Changes:**
            - Merged commits from upstream/main
            - Review carefully for potential conflicts or breaking changes

            **Checklist before merge:**
            - [ ] Review upstream commits for compatibility
            - [ ] Run security audit if needed (see `claude.md`)
            - [ ] Test locally before merging
            - [ ] Ensure licensing and co-authorship are preserved

            **After merge:**
            - Sync `nightly` branch: `git checkout nightly && git merge main && git push`
            - Rerun security audit if significant changes detected

            ---
            *Generated by [GitHub Actions Sync Workflow](/.github/workflows/sync-upstream.yml)*
            *Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")*
          labels: |
            automated
            upstream-sync

      - name: Summary
        if: steps.check.outputs.changes == 'false'
        run: |
          echo "✅ No upstream changes detected. Fork is up to date."
```

### Appendix C: Add SPDX License Headers (Script)

Create `scripts/add_license_headers.py`:

```python
#!/usr/bin/env python3
"""
Add SPDX license identifiers to source files.
Usage: python scripts/add_license_headers.py
"""

import os
from pathlib import Path

PYTHON_HEADER = """# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 SurfSense Contributors
"""

TYPESCRIPT_HEADER = """// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 SurfSense Contributors
"""

def add_header_to_file(filepath: Path, header: str):
    """Add license header to file if not already present."""
    content = filepath.read_text(encoding='utf-8')

    if 'SPDX-License-Identifier' in content:
        print(f"⏭️  Skipping {filepath} (already has header)")
        return False

    new_content = header + '\n' + content
    filepath.write_text(new_content, encoding='utf-8')
    print(f"✅ Added header to {filepath}")
    return True

def main():
    root = Path(__file__).parent.parent
    count = 0

    # Python files
    for py_file in root.rglob('*.py'):
        if 'venv' in str(py_file) or 'node_modules' in str(py_file):
            continue
        if add_header_to_file(py_file, PYTHON_HEADER):
            count += 1

    # TypeScript/JavaScript files
    for ts_file in root.rglob('*.ts'):
        if 'node_modules' in str(ts_file):
            continue
        if add_header_to_file(ts_file, TYPESCRIPT_HEADER):
            count += 1

    for tsx_file in root.rglob('*.tsx'):
        if 'node_modules' in str(tsx_file):
            continue
        if add_header_to_file(tsx_file, TYPESCRIPT_HEADER):
            count += 1

    print(f"\n✅ Added license headers to {count} files")

if __name__ == '__main__':
    main()
```

Run with: `python scripts/add_license_headers.py`

---

## Site Configuration System

**Implementation Date:** 2025-11-18
**Implemented By:** Claude AI Assistant (Anthropic Sonnet 4.5)
**Feature:** Dynamic Site Appearance Configuration

### Overview

The site configuration system provides administrators with a centralized, database-driven approach to control the visibility and behavior of homepage elements, navigation links, footer sections, and route availability. This eliminates hardcoded UI elements and enables runtime customization without code changes.

### Architecture

**Backend Stack:**
- **Database:** PostgreSQL singleton pattern (single row with id=1)
- **ORM:** SQLAlchemy with AsyncSession
- **Migration:** Alembic migration #38
- **API Framework:** FastAPI with Pydantic validation
- **Access Control:** Superuser-only admin endpoints, public read endpoint

**Frontend Stack:**
- **State Management:** React Context API (SiteConfigContext)
- **UI Framework:** Next.js 15.5.6 App Router
- **Conditional Rendering:** Client-side based on configuration
- **Route Guards:** RouteGuard component for disabled routes

### Database Schema

**Table:** `site_configuration` (singleton - only 1 row)

```sql
CREATE TABLE site_configuration (
    id INTEGER PRIMARY KEY,  -- Always 1 (singleton)

    -- Header/Navbar toggles
    show_pricing_link BOOLEAN DEFAULT FALSE,
    show_docs_link BOOLEAN DEFAULT FALSE,
    show_github_link BOOLEAN DEFAULT FALSE,
    show_sign_in BOOLEAN DEFAULT TRUE,

    -- Homepage toggles
    show_get_started_button BOOLEAN DEFAULT FALSE,
    show_talk_to_us_button BOOLEAN DEFAULT FALSE,

    -- Footer toggles
    show_pages_section BOOLEAN DEFAULT FALSE,
    show_legal_section BOOLEAN DEFAULT FALSE,
    show_register_section BOOLEAN DEFAULT FALSE,

    -- Route disabling
    disable_pricing_route BOOLEAN DEFAULT TRUE,
    disable_docs_route BOOLEAN DEFAULT TRUE,
    disable_contact_route BOOLEAN DEFAULT TRUE,
    disable_terms_route BOOLEAN DEFAULT TRUE,
    disable_privacy_route BOOLEAN DEFAULT TRUE,

    -- Custom text
    custom_copyright VARCHAR(200) DEFAULT 'SurfSense 2025',

    CONSTRAINT check_singleton CHECK (id = 1)
);
```

**Migration:** `surfsense_backend/alembic/versions/38_add_site_configuration_table.py`

### API Endpoints

#### 1. Public Configuration (Unauthenticated)

```http
GET /api/v1/site-config/public
```

**Response:**
```json
{
  "show_pricing_link": false,
  "show_docs_link": false,
  "show_github_link": false,
  "show_sign_in": true,
  "show_get_started_button": false,
  "show_talk_to_us_button": false,
  "show_pages_section": false,
  "show_legal_section": false,
  "show_register_section": false,
  "disable_pricing_route": true,
  "disable_docs_route": true,
  "disable_contact_route": true,
  "disable_terms_route": true,
  "disable_privacy_route": true,
  "custom_copyright": "SurfSense 2025"
}
```

#### 2. Admin Configuration (Superuser Only)

```http
GET /api/v1/site-config
Authorization: Bearer <jwt_token>
```

**Response:** Same as public endpoint

#### 3. Update Configuration (Superuser Only)

```http
PUT /api/v1/site-config
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "show_pricing_link": true,
  "custom_copyright": "© MyCompany 2025"
}
```

**Response:** Updated configuration object

### Frontend Integration

#### 1. Global Context

**File:** `surfsense_web/contexts/SiteConfigContext.tsx`

```typescript
const { config, isLoading, error, refetch } = useSiteConfig();

// Access any configuration value
const showPricing = config.show_pricing_link;
const copyright = config.custom_copyright;
```

**Initialization:** Wrapped in `app/layout.tsx` for global availability

#### 2. Conditional Rendering Examples

**Navbar** (`components/homepage/navbar.tsx`):
```tsx
{config.show_pricing_link && !config.disable_pricing_route && (
  <Link href="/pricing">Pricing</Link>
)}

{config.show_github_link && (
  <Link href="https://github.com/okapteinis/SurfSense">
    <IconBrandGithub />
  </Link>
)}
```

**Homepage Hero** (`components/homepage/hero-section.tsx`):
```tsx
{config.show_get_started_button && (
  <Link href="/register" className="btn-primary">
    Get Started
  </Link>
)}
```

**Footer** (`components/homepage/footer.tsx`):
```tsx
<p>&copy; {config.custom_copyright || "SurfSense 2025"}</p>

{config.show_legal_section && (
  <div>
    {!config.disable_terms_route && <Link href="/terms">Terms</Link>}
    {!config.disable_privacy_route && <Link href="/privacy">Privacy</Link>}
  </div>
)}
```

#### 3. Route Guarding

**File:** `components/RouteGuard.tsx`

```tsx
<RouteGuard routeKey="pricing">
  <PricingPage />
</RouteGuard>
```

**Protected Routes:**
- `/pricing` → checks `disable_pricing_route`
- `/contact` → checks `disable_contact_route`
- `/terms` → checks `disable_terms_route`
- `/privacy` → checks `disable_privacy_route`

**Behavior:** Redirects to `/404` if route is disabled

### Admin Panel

**Location:** `/dashboard/site-settings`

**Features:**
- ✅ Visual toggle switches for all boolean flags
- ✅ Text input for custom copyright
- ✅ Real-time updates via API
- ✅ Organized by section (Header, Homepage, Footer, Routes, Custom Text)
- ✅ Descriptions for each toggle
- ✅ Save button with loading state
- ✅ Toast notifications for success/error

**Access Control:** Requires superuser authentication (JWT token)

**UI Components:**
- Custom ToggleSwitch component with animated transitions
- Gradient save button matching brand colors
- Dark mode support
- Responsive design (mobile-friendly)

### Configuration Options

#### Header & Navigation
| Toggle | Description | Default |
|--------|-------------|---------|
| `show_pricing_link` | Show pricing link in navbar | `false` |
| `show_docs_link` | Show docs link in navbar | `false` |
| `show_github_link` | Show GitHub icon in navbar | `false` |
| `show_sign_in` | Show sign in button | `true` |

#### Homepage Buttons
| Toggle | Description | Default |
|--------|-------------|---------|
| `show_get_started_button` | Show "Get Started" CTA button | `false` |
| `show_talk_to_us_button` | Show "Talk to Us" CTA button | `false` |

#### Footer Sections
| Toggle | Description | Default |
|--------|-------------|---------|
| `show_pages_section` | Show pages section (Pricing, Docs, Contact) | `false` |
| `show_legal_section` | Show legal section (Terms, Privacy) | `false` |
| `show_register_section` | Show register section (Sign Up, Sign In) | `false` |

#### Route Disabling
| Toggle | Description | Default |
|--------|-------------|---------|
| `disable_pricing_route` | Disable /pricing route (404) | `true` |
| `disable_docs_route` | Disable /docs route (404) | `true` |
| `disable_contact_route` | Disable /contact route (404) | `true` |
| `disable_terms_route` | Disable /terms route (404) | `true` |
| `disable_privacy_route` | Disable /privacy route (404) | `true` |

#### Custom Text
| Field | Description | Default |
|-------|-------------|---------|
| `custom_copyright` | Footer copyright text (max 200 chars) | `"SurfSense 2025"` |

### Security Considerations

1. **Access Control:**
   - Admin endpoints require `is_superuser = true`
   - Public endpoint is read-only and unauthenticated
   - JWT token validation on all admin operations

2. **Input Validation:**
   - Pydantic schemas enforce data types
   - String length limits (copyright max 200 chars)
   - Boolean validation for all toggles

3. **Singleton Pattern:**
   - Database constraint ensures only 1 configuration row
   - `get_or_create_config()` helper prevents missing config
   - Atomic updates via SQLAlchemy transactions

4. **Client-Side Security:**
   - Configuration fetched at app startup
   - No sensitive data exposed (public-facing settings only)
   - RouteGuard prevents access to disabled routes

### Migration Guide

#### Step 1: Apply Database Migration

```bash
cd surfsense_backend
alembic upgrade head
```

This creates the `site_configuration` table and inserts the default row.

#### Step 2: Verify Configuration

```bash
# Check that singleton row exists
psql -d surfsense -c "SELECT * FROM site_configuration WHERE id = 1;"
```

#### Step 3: Access Admin Panel

1. Log in as superuser
2. Navigate to `/dashboard/site-settings`
3. Configure toggles as desired
4. Click "Save Configuration"

#### Step 4: Verify Frontend Changes

1. Visit homepage at `/`
2. Check navbar for conditional links
3. Check footer for conditional sections
4. Test disabled routes (should show 404)

### Testing Checklist

- [x] Database migration runs successfully
- [x] Singleton row created with default values
- [x] Public API endpoint returns configuration (unauthenticated)
- [x] Admin GET endpoint requires authentication
- [x] Admin PUT endpoint requires superuser role
- [x] Frontend context loads configuration on app startup
- [x] Navbar shows/hides links based on config
- [x] Homepage shows/hides buttons based on config
- [x] Footer shows/hides sections based on config
- [x] Custom copyright displays correctly
- [x] RouteGuard redirects disabled routes to 404
- [x] Admin panel UI loads and displays current config
- [x] Admin panel saves changes successfully
- [x] Changes reflect immediately after save (via refetch)

### Files Changed

**Backend:**
```
surfsense_backend/app/db.py                                      # Added SiteConfiguration model
surfsense_backend/alembic/versions/38_add_site_configuration_table.py  # Migration
surfsense_backend/app/schemas/site_configuration.py              # Pydantic schemas
surfsense_backend/app/routes/site_configuration_routes.py        # API routes
surfsense_backend/app/routes/__init__.py                         # Route registration
```

**Frontend:**
```
surfsense_web/contexts/SiteConfigContext.tsx                     # React context
surfsense_web/app/layout.tsx                                     # Context provider
surfsense_web/components/RouteGuard.tsx                          # Route guard component
surfsense_web/components/homepage/navbar.tsx                     # Conditional navbar
surfsense_web/components/homepage/hero-section.tsx               # Conditional buttons
surfsense_web/components/homepage/footer.tsx                     # Conditional footer
surfsense_web/app/(home)/pricing/page.tsx                        # Route guard
surfsense_web/app/(home)/contact/page.tsx                        # Route guard
surfsense_web/app/(home)/terms/page.tsx                          # Route guard
surfsense_web/app/(home)/privacy/page.tsx                        # Route guard
surfsense_web/app/dashboard/site-settings/page.tsx               # Admin UI
```

### Benefits

1. **No Code Deployments:** Site appearance changes without code changes
2. **Self-Service:** Administrators manage UI without developer intervention
3. **Branding Flexibility:** Custom copyright text for white-label deployments
4. **Privacy-Focused:** Disable routes/features you don't need
5. **Minimal UI:** Default configuration hides all non-essential elements
6. **Type Safety:** Full TypeScript support with validated schemas
7. **Performance:** Configuration cached in React context (no repeated API calls)
8. **Scalability:** Singleton pattern ensures consistent state across all users

### Future Enhancements

**Potential additions (not yet implemented):**
- Multi-tenant configurations (per-user or per-organization)
- Custom navigation links (dynamic menu items)
- Theme color customization
- Logo upload and management
- Custom homepage headline/tagline
- Feature flag management for experimental features
- Analytics opt-out configuration
- GDPR compliance toggles

### Comparison to Previous Approach

**Before (Hardcoded):**
- UI elements always visible
- Changes required code modifications
- No runtime customization
- Developer-only control

**After (Database-Driven):**
- UI elements conditionally rendered
- Changes via admin panel
- Runtime customization
- Self-service for admins

### Support

For questions or issues related to site configuration:
- Review API documentation: `surfsense_backend/app/routes/site_configuration_routes.py`
- Check schema definitions: `surfsense_backend/app/schemas/site_configuration.py`
- Examine frontend context: `surfsense_web/contexts/SiteConfigContext.tsx`
- Access admin panel: `/dashboard/site-settings`

---

## Conclusion

**Overall Security Posture:** ✅ **STRONG**

SurfSense demonstrates excellent security practices with automated tooling (detect-secrets, pre-commit hooks, bandit), no hardcoded secrets, and comprehensive architecture. The codebase is well-structured, uses modern technologies (Python 3.12, React 19, Next.js 15), and implements advanced RAG techniques with proper security controls (user isolation, search space filtering).

**Key Strengths:**
- ✅ Automated secret scanning with detect-secrets
- ✅ Pre-commit hooks for security and code quality
- ✅ No real secrets in codebase (all placeholders verified)
- ✅ Modern, actively maintained tech stack
- ✅ Advanced RAG architecture (2-tier hierarchical + hybrid search)
- ✅ Comprehensive LLM support (100+ providers via LiteLLM)
- ✅ Excellent documentation (multi-language support)
- ✅ Apache 2.0 license (permissive, commercial-friendly)

**Critical Actions Required:**
- None (no critical vulnerabilities found)

**High-Priority Improvements:**
1. Enhance .gitignore (10 min)
2. Add Docker non-root user (5 min)

**Medium-Priority Enhancements:**
3. Add SPDX license identifiers (2 hours, automatable)
4. Document upstream sync automation (1 hour)
5. Add resource limits to docker-compose.yml (30 min)

**Audit Certification:**
This repository is **APPROVED** for continued development and production deployment with implementation of high-priority recommendations.

---

**Audit Completed:** 2025-11-17
**Next Audit Recommended:** 2025-12-17 (or after major upstream merge)

**Co-Authors:**
- Ojārs Kapteiņš <ojars@kapteinis.lv> - Audit Requester & Repository Maintainer
- Claude AI Assistant (Anthropic Sonnet 4.5) - Security & Architecture Audit

---

*This audit report is licensed under CC BY 4.0. The audited code remains under Apache License 2.0.*
