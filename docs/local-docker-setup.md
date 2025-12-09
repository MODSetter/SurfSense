# Local Docker Setup Guide

This guide covers common configuration issues when running SurfSense locally with Docker.

## Environment Configuration

### `.env` File (Project Root)

Create a `.env` file in the project root with these settings:

```bash
# Docker Specific Env's

# Celery Config
REDIS_PORT=6379  # Must be 6379 for internal container communication
FLOWER_PORT=5555

# Frontend Configuration
FRONTEND_PORT=3000
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE=LOCAL
NEXT_PUBLIC_ETL_SERVICE=DOCLING

# Backend Configuration
BACKEND_PORT=8000

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=surfsense
POSTGRES_PORT=5432

# pgAdmin Configuration
PGADMIN_PORT=5050
PGADMIN_DEFAULT_EMAIL=admin@surfsense.com
PGADMIN_DEFAULT_PASSWORD=your_secure_password
```

> **Important**: If you change any `NEXT_PUBLIC_*` variables, you must rebuild the frontend container since these are baked in at build time.

## LLM Provider Configuration

### OpenAI
- **Provider**: OpenAI
- **API Key**: Your OpenAI API key
- **API Base**: Leave empty (uses default)

### Ollama (Local LLMs)

When running Ollama on your host machine (outside Docker):

- **Provider**: Ollama
- **API Base**: `http://host.docker.internal:11434`
- **Model Name**: e.g., `qwen3:30b`, `gemma3:27b`, `deepseek-r1:32b`

> **Why `host.docker.internal`?** The backend runs inside a Docker container. From inside the container, `localhost` refers to the container itself, not your Mac. `host.docker.internal` is a special DNS name that Docker Desktop provides to reach services on the host machine.

### Other Local LLM Providers

For any LLM service running on your host machine (LM Studio, LocalAI, etc.), use:
```
http://host.docker.internal:<PORT>
```

## Common Issues

### "Failed to fetch" when setting up LLM provider

1. **Check backend is running**: `curl http://localhost:8000/docs`
2. **Check backend logs**: `docker compose logs backend --tail=50`
3. **For Ollama**: Ensure API Base is `http://host.docker.internal:11434`, not `localhost`

### Redis connection errors

If you see errors like:
```
Cannot connect to redis://redis:16379/0: Connection refused
```

Ensure `REDIS_PORT=6379` in your `.env` file. The internal container port must always be 6379.

### Cannot create account / login issues

Ensure `NEXT_PUBLIC_FASTAPI_BACKEND_URL` uses `localhost` (not `host.docker.internal`). This URL is used by your browser, which runs on your host machine.

## Rebuilding After Configuration Changes

```bash
# Stop all containers
docker compose down

# Rebuild (use --no-cache if changing NEXT_PUBLIC_* vars)
docker compose build --no-cache

# Start containers
docker compose up -d

# Check logs
docker compose logs -f
```

## Verifying Services

```bash
# Backend API docs
curl http://localhost:8000/docs

# Ollama (if installed)
curl http://localhost:11434/api/tags

# Backend logs
docker compose logs backend --tail=50
```
