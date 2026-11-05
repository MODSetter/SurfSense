# ADR 0085: A user can move models or all data to another drive, and Electron's settings stay behind

- **Status:** Accepted
- **Date:** 2026-11-05
- **Source:** maintainer decision, 5 Nov 2026 (no permalink)

## Context

Users with little room on their default drive asked to keep downloaded models elsewhere. Uploads and Studio outputs can be large too, so moving only models does not cover everyone. Everything lived under one fixed folder, and Electron has no path for models: `app.setPath` cannot help, because SurfSense computes these folders itself.

## Decision

- Two settings: the models folder, and all data. Models follow the data until moved on their own.
- `electron/`, holding the secret and Chromium's profile, stays in the fixed folder with the file that says where the rest went. A location cannot live in the folder it locates, and a secret on an unplugged drive would be replaced by a new one, orphaning every stored API key.
- The move copies, reads every file back, switches the location in one step, and deletes the original only after the next start has answered from the new folder.
- Absolute paths in the copied databases are rewritten rather than kept valid with a link left at the old path. A link would break on a second move and on the old drive's removal.

## Consequences

- A moved data folder needs its drive at startup, and the app stops and asks rather than making an empty database. A moved models folder only limits what runs.
- A backup of a moved install spans two folders.
- The rewrite of `opencode.db` covers every text column rather than naming opencode's schema, so an opencode update does not silently miss a new column, and the copy is what changes, so a bad rewrite cannot reach the original.
