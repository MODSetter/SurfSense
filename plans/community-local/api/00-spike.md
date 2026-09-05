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
- Document dev vs packaged binary paths.
- Sidecar pattern — separate binaries, not threads in Electron.
- Build per OS on that OS.

## Acceptance

- VM without Python → app opens → `/health` OK → one Huey job runs → quit, no orphan processes.
- The same binary creates its database and answers a query against `chunk_vectors`.

## Out of scope

Docling, real UI, model downloads.

## Stack

**FastAPI** — confirmed stack for all API phases. Spike validates PyInstaller packaging, not whether to use FastAPI.
