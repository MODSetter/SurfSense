# API — Phase 5: Packaging

## Goal

Installers for Paths A / B / C.

## Work

- PyInstaller specs: `surfsense-api` + `surfsense-worker` (`--onedir`; worker hiddenimports from [`../worker/05-packaging.md`](../worker/05-packaging.md)).
- electron-builder `extraResources` → `resources/backend/`.
- CI: win/mac/linux; smoke `/health`.
- Models outside exe — `~/.surfsense/models/`.
- Manifest or routes for model pack URLs (frontend download UI).

## Acceptance

- Clean VM Path B: install → wizard → upload → chat.
- Quit → no orphan `surfsense-*` processes.
