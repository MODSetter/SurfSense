# API — Phase 0: Spike

> Owns: `electron/`, PyInstaller API binary. Worker echo: [`../worker/01-boot.md`](../worker/01-boot.md).

## Goal

Packaged Electron spawns API + worker binaries; `/health`; clean quit.

## Work

- Minimal FastAPI `/health` + PyInstaller spec (`--onedir`).
- **Open the database in the frozen binary** — migrations from bundled
  `alembic/versions/` and the sqlite-vec extension from `sqlite_vec/vec0.so`,
  neither named by an import statement, so PyInstaller drops both unless told.
  ✓ Proven and kept as a guard: `tests/packaging/test_frozen_boot.py`
  (`pytest -m packaging`) freezes a binary that migrates, loads `vec0`, and
  round-trips a vector. Recipe in
  [`05-packaging.md`](05-packaging.md#proven-the-frozen-binary-opens-its-database).
- Electron spawn/kill sidecars from `extraResources`.
  ✓ Dev proven: `electron/src/main/sidecars.ts` spawns the API + worker in their
  own process group, waits on `/health`, and reaps both on quit (SIGTERM →
  SIGKILL; `taskkill /t` on Windows). `pnpm check:sidecars` asserts no orphans.
  Packaged spawn from `extraResources` (frozen binaries) stays phase 5.
  Shape borrowed from mature Electron+Python apps (modly `PythonBridge`,
  OpenHands): readiness fails fast if a sidecar exits mid-startup rather than
  polling the full timeout; `app.requestSingleInstanceLock()` stops a second
  instance from fighting over the SQLite file and port; an unexpected sidecar
  exit is flagged as a crash (`sidecar:crashed`), not a silent stop.
- Document dev vs packaged binary paths. ✓ `sidecars.ts`: dev runs `uv run
  main.py` / `worker.py`; packaged runs `resources/api` / `resources/worker`.
- Sidecar pattern — separate binaries, not threads in Electron. ✓ Two child
  processes, not threads.
- Build per OS on that OS.

## Acceptance

- VM without Python → app opens → `/health` OK → one Huey job runs → quit, no orphan processes.
  ◐ Dev covers `/health` OK and quit-no-orphans (`pnpm check:sidecars`); the
  packaged-on-a-clean-VM leg lands with the frozen binaries in phase 5.
- The same binary creates its database and answers a query against `chunk_vectors`.
  ✓ `tests/packaging/test_frozen_boot.py` (see above).

## Out of scope

Docling, real UI, model downloads.

## Stack

**FastAPI** — confirmed stack for all API phases. Spike validates PyInstaller packaging, not whether to use FastAPI.
