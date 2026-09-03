# API — Phase 0: Spike

> Owns: `electron/`, PyInstaller API binary. Worker echo: [`../worker/01-boot.md`](../worker/01-boot.md).

## Goal

Packaged Electron spawns API + worker binaries; `/health`; clean quit.

## Work

- Minimal FastAPI `/health` + PyInstaller spec (`--onedir`).
- Electron spawn/kill sidecars from `extraResources`.
- Document dev vs packaged binary paths.
- Sidecar pattern — separate binaries, not threads in Electron.
- Build per OS on that OS.

## Acceptance

- VM without Python → app opens → `/health` OK → one Huey job runs → quit, no orphan processes.

## Out of scope

SQLite schema, Docling, real UI, model downloads.

## Stack

**FastAPI** — confirmed stack for all API phases. Spike validates PyInstaller packaging, not whether to use FastAPI.
