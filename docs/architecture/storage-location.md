# Storage location

Settings › Storage moves the downloaded models, or all of a user's data, to another drive. The model step of onboarding offers the models half through a link beside the Hugging Face search, which opens on the current folder, and a download refused for disk space offers it too. The Docker image has no such setting: its folder is the volume it mounts.

**Code:** [`surfsense_local/electron/src/main/storage/`](../../surfsense_local/electron/src/main/storage/), [`surfsense_local/frontend/src/features/storage/`](../../surfsense_local/frontend/src/features/storage/), [`surfsense_local/sidecars/model-folders.ts`](../../surfsense_local/sidecars/model-folders.ts)
**Decisions:** [ADR 0084](../adr/0084-the-data-folder-moves-and-electrons-settings-stay.md)

```text
  ~/.surfsense                 fixed: electron/, storage-location.json, api-url
  <dataRoot>/                  moved or not: surfsense.db, data/, agent/, ...
  <modelsRoot>/                moved or not: models/ audio/ images/ embeddings/
```

`dataRoot` defaults to the fixed folder and `modelsRoot` to `dataRoot`, so models follow the data until they are moved on their own. Boot passes each folder through `BootContext`; the API and workers hear `SURFSENSE_LOCAL_DATA_DIR`, `SURFSENSE_LOCAL_EMBEDDING_MODELS_DIR` and `SURFSENSE_LOCAL_SHELL_SETTINGS_DIR`. A change needs a restart, because every sidecar takes its folders at launch.

## What stays behind

`electron/` never moves: Chromium holds its files open, and `secret.bin` must not depend on a drive, since `loadSecret` mints a new secret when it cannot read one and that orphans every stored API key. `api-url` stays because `surfsense-plugins` looks for it in the home folder. A backup of a moved install therefore spans two folders.

The bundled packs in the app's `resources/models` stay with the app.

## Choosing a folder

The page names a kind and never a path. Main opens the picker and keeps the plan, so a compromised page cannot aim the mover at a folder of its own (`storage-ipc.ts`).

`planMove` changes nothing and refuses a folder before any copying. SurfSense always works in its own subfolder, `SurfSense-Models` or `SurfSense-Data`, so nothing of the user's is in the way.

| Refusal | Why |
|---|---|
| `same_folder` | Already there |
| `inside_current` | The move would copy into itself |
| `inside_app` | An update deletes the app's folder |
| `network_drive` | All data only: SQLite's locks do not hold on a share |
| `not_writable` | A test write failed |
| `no_large_files` | FAT32: extending a test file past 4 GiB failed, and models are often larger. Tried only with 5 GiB free, since a full drive fails the same way |
| `no_hard_links` | All data only: exFAT and FAT32. The agent's text cache hard-links into each thread |
| `not_enough_room` | The size to move plus 1 GiB, the same margin a download keeps |
| `target_occupied` | The subfolder holds files with no marker: merging would mix them |

Measured on real APFS, exFAT and FAT32 volumes on macOS. A folder that already holds a marker is switched to with nothing copied, and the current copy stays.

## The move

It runs in the open app, not on the next start: boot shows no window until the API answers, so a move there would have nothing on screen.

1. Ask about running replies, tell the page to cover itself, then stop every sidecar. The entries to move are listed again here: a database's `-wal` may have gone with its process.
2. Record `movingTo`, so a crash's partial copy is removed at the next start.
3. Copy into `.incoming-<kind>` under the target, keeping hard links as links, modes and modified times. A symbolic link pointing inside the old folder is repointed.
4. Read every copied file back and compare its SHA-256. The originals may be deleted on the strength of this.
5. Repoint what stores absolute paths, in the copy (below).
6. Rename into place, write the marker, then replace `storage-location.json` in one step. Until that write the old folder is still in charge, and any failure removes the copy.
7. Relaunch, or under `pnpm dev` only quit, because Electron's exit also takes Vite down. Once the new API has answered, `removeOldCopies` deletes only the entries the move named, because the old folder may be the user's home. A drive that is away keeps its record for a later start.

Cancelling, or a failure, relaunches on the old folder. A closed window waits while a move copies.

## What stores absolute paths

| Where | Handling |
|---|---|
| `models/models.ini` | Deleted from the copy; the API writes it at startup |
| `audio/server.json`, `audio/transcription.json` | Paths under the old folder rewritten, with forward slashes |
| `opencode.db`, every text column | Rewritten. opencode runs every call about a session in the folder it stored, so without this each thread reads as legacy. Measured on opencode 2.1.2 |
| `surfsense.db`, `claude_session_entries` only | Rewritten. A user's documents may quote any path, so no other table is touched |

Each folder is matched with its separator, so `/a/b` cannot match `/a/b-other`, under each spelling it is stored in: as written, with forward slashes, escaped inside JSON, and as Python's `\uXXXX`.

## A drive that is away

A moved folder carries a marker, `.surfsense-storage`. `settleStorageBeforeBoot` runs before anything starts, because on Linux a disconnected drive leaves an empty mount point that accepts writes on the wrong disk, and an API on an empty folder makes a fresh database, which looks like the user's data is gone.

- **Data folder away:** Try again, Choose folder or Quit. SurfSense cannot start without it.
- **Models folder away:** Try again, Continue without local models, or Quit. Continuing gives the runtimes an empty stand-in, `.models-unavailable`, and `SURFSENSE_LOCAL_MODEL_STORAGE_UNAVAILABLE` makes every download refuse with `model_storage_unavailable`, so nothing lands on the wrong drive. The section shows the drive as not connected, with Change disabled.

## Platforms

- **Windows:** a directory link is copied as a junction, which needs no privilege. Renames retry while antivirus holds a new file.
- **macOS:** the folder a move may not enter is the whole `.app` bundle. The app is not sandboxed, so `NSRemovableVolumesUsageDescription` and its siblings in `electron-builder.yml` are all it needs; security-scoped bookmarks apply only to Mac App Store builds.
- **Linux:** AppImage, deb and rpm reach any mounted drive. An AppImage relaunches from `$APPIMAGE`, because its running path is a mount that goes when it exits. A confined snap reaches none without the `removable-media` plug, so the bridge and the section are absent there.

## Known gaps

- A network drive is detected only by a UNC path on Windows and by filesystem type on Linux. A mapped Windows drive and a macOS network volume pass the check, and the data folder's SQLite locks are then unreliable.
- A drive mounted `noexec` on Linux passes the checks, but staged runtimes under a moved data folder would not run.
- A snap offers no move.
