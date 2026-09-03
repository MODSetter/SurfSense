# API — Phase 5: Packaging

## Goal

Installers for Paths A / B / C.

## Work

- PyInstaller specs: `surfsense-api` + `surfsense-worker` (`--onedir`; worker hiddenimports from [`../worker/05-packaging.md`](../worker/05-packaging.md)).
- **`collect_dynamic_libs('sqlite_vec')`** in both specs — see below.
- `alembic/versions/` as spec data; the packaged app runs migrations on launch.
- electron-builder `extraResources` → `resources/backend/`.
- CI: win/mac/linux; smoke `/health`.
- Models outside exe — `~/.surfsense/models/`.
- Manifest or routes for model pack URLs (frontend download UI).

## Files no import statement names

PyInstaller decides what to bundle by following `import` statements through the
bytecode. Anything reached by a path at runtime is invisible to it, and the app
that works from source starts failing only once it is frozen — on a clean
machine, per OS, at the end of the project.

| File | Reached by | Symptom if dropped |
|---|---|---|
| `sqlite_vec/vec0.so` | `conn.load_extension(path)` from C | **App will not start.** Every connection loads the extension, so the migration on launch is the first thing to die |
| `alembic/versions/*.py` | Alembic reads the directory | No revisions found; an empty database stays empty |
| Docling parser models | downloaded or bundled data | Every ingest fails |

## Acceptance

- Clean VM Path B: install → wizard → upload → chat.
- Quit → no orphan `surfsense-*` processes.
