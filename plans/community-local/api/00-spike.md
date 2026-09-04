# API — Phase 0: Spike

> Owns: `electron/`, PyInstaller API binary. Worker echo: [`../worker/01-boot.md`](../worker/01-boot.md).

## Goal

Packaged Electron spawns API + worker binaries; `/health`; clean quit.

## Work

- Minimal FastAPI `/health` + PyInstaller spec (`--onedir`).
- **Open the database in the frozen binary**, which means migrations running from
  bundled `alembic/versions/` and the sqlite-vec extension loading from
  `sqlite_vec/vec0.so`. Neither is named by an import statement, so PyInstaller
  drops both unless told, and the app then fails on its first connection. Cheap
  to prove here; expensive to find in [phase 5](05-packaging.md).
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
