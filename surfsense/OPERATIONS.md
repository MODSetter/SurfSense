# SurfSense Operations Runbook (Local Self-Hosted)

This runbook standardizes day-2 operations for the Docker stack in this folder.

## 0) Scope and conventions
- Working directory: `surfsense/`
- Compose project: `surfsense` (`name: surfsense` in compose)
- Primary user endpoints (from `.env` defaults):
  - Frontend: `http://127.0.0.1:3929`
  - Backend: `http://127.0.0.1:8929/health`
  - Zero-cache: `http://127.0.0.1:5929/keepalive`

## 1) Start / Stop / Restart
```bash
cd /home/vitrus/work/SurfSense/surfsense

# Start
docker compose up -d

# Stop
Docker compose down

# Restart only app-tier services (keeps DB/Redis running)
Docker compose restart backend frontend zero-cache gateway
```

## 2) One-command health check
```bash
bash scripts/health-check.sh
```
Checks:
- container states and health fields
- frontend/backend/zero-cache/searxng HTTP probes

## 3) Logs and quick diagnostics
```bash
# Follow app logs
docker compose logs -f --tail=200 backend frontend zero-cache gateway

# Follow dependency logs
docker compose logs -f --tail=200 db redis searxng

# Backend errors in last lines
docker compose logs --tail=300 backend | egrep -i "error|exception|traceback"
```

## 4) Database backup and restore
### Backup
```bash
bash scripts/backup-postgres.sh
# or custom backup dir:
bash scripts/backup-postgres.sh /home/vitrus/work/SurfSense/surfsense/backups
```

### Restore (destructive)
```bash
bash scripts/restore-postgres.sh /path/to/surfsense-db-YYYYmmdd-HHMMSS.sql.gz
```
Restore script asks for explicit `RESTORE` confirmation.

## 5) Safe update workflow (version pinning + health gate)
1. Choose a pinned image tag (avoid `latest` in steady-state).
2. Back up DB.
3. Run update script:
```bash
bash scripts/update-surfsense.sh <version-tag>
```
4. If health check fails, rollback by restoring previous `SURFSENSE_VERSION` in `.env` and redeploy:
```bash
docker compose up -d
bash scripts/health-check.sh
```

## 6) Security baseline
- Rotate away from defaults in `.env`:
  - `SECRET_KEY`
  - `DB_PASSWORD`
  - `ZERO_ADMIN_PASSWORD`
  - any OAuth secrets
- Keep `ZERO_NUM_SYNC_WORKERS` <= both:
  - `ZERO_UPSTREAM_MAX_CONNS`
  - `ZERO_CVR_MAX_CONNS`
- Avoid exposing DB/Redis publicly unless required.

## 7) Recommended operator cadence
- Daily: `bash scripts/health-check.sh`
- Before any update: run backup script
- After update: run health check and inspect logs for 5–10 min
