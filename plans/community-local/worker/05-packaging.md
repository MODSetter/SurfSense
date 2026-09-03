# Worker — Phase 5: Packaged worker

## Goal

Docling, torch, and **sqlite-vec** run inside the PyInstaller-built worker binary.

## Work

- Worker spec hiddenimports (`docling_parse`, torch CPU, `sqlite_vec`, etc.).
- **Bundle sqlite-vec loadable extension** for target OS; verify `sqlite_vec.load()` in packaged binary (same as dev).
- Smoke on CI artifact from [`../api/05-packaging.md`](../api/05-packaging.md): ingest PDF → FTS + vec0 query both return hits.
- RAM note: Docling RSS on dev machine.

## Acceptance

- Packaged app: upload PDF → ingest + hybrid search without system Python or manual extension install.
