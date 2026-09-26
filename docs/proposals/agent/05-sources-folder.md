# A folder on disk as the Sources root

> The user picks a folder, and its files stay where they are. SurfSense indexes them in place, watches the folder, re-reads a file with Docling when its content changes, and does not write to the folder in this phase. Git is not the storage.

## Today

- An upload is copied to `data/workspaces/<workspace>/documents/<document>/original.<ext>`. The path is built from row ids, "so nothing else a user types reaches the filesystem" ([documents](../../architecture/documents.md)).
- Documents have no folders; there is no `folder_id` ([data model](../../architecture/data-model.md), Known gaps).
- No code watches files on disk. None of `modules/`, `worker/`, `shared/` or the Electron main process uses a file watcher.
- The desktop app has no git-backed store ([ADR 0003](../../adr/0003-artifacts-as-documents.md)).

## Decisions

- **Link, don't copy.** Each file in the linked folder gets an index row: relative path, size, `st_mtime_ns`, file identity, SHA-256 of its content, and the document it produced. Schema changes are hand-written Alembic revisions ([ADR 0005](../../adr/0005-hand-written-migrations.md)).
- **Watch, then reconcile.** A file event is a hint to check that path. A full scan reconciles the index at startup, on a timer, after the machine wakes, and after a watcher error.
- **Re-read only on change.** Docling runs again only when a file's content hash changes. A delete and a create are paired as a move by file identity, and otherwise by size and hash.
- **Read in place.** Ingestion reads a linked file where it is. That ends the rule that only row-id paths reach the filesystem, so every path is resolved and checked to be inside the linked folder before it is used.
- **No writes.** Nothing writes to the linked folder in this phase.

## Libraries and platform facts

- **Watching: `watchfiles`** (MIT). The desktop backend already locks 1.2.0, through `uvicorn[standard]` ([`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml), [`uv.lock`](../../../surfsense_local/backend/uv.lock)). Its Rust layer at [v1.2.0](https://github.com/samuelcolvin/watchfiles/blob/v1.2.0/src/lib.rs) has no handling for the underlying `notify` crate's rescan signal, so an overflow of events is not reported, which is why the reconcile scan is required. It has a `force_polling` option and a `WATCHFILES_FORCE_POLLING` environment variable for drives where native events do not work ([`watchfiles/main.py`](https://github.com/samuelcolvin/watchfiles/blob/v1.2.0/watchfiles/main.py)).
- **Hashing: the standard library.** Use [`hashlib.file_digest`](https://docs.python.org/3/library/hashlib.html#hashlib.file_digest) with SHA-256 (Python 3.11 and later; the backend pins 3.12). Skip hashing when size, `st_mtime_ns` and identity are unchanged.
- **Identity: `st_dev` and `st_ino` from `os.stat()`.** On Windows, [`os.DirEntry.stat()`](https://docs.python.org/3.12/library/os.html#os.DirEntry.stat) always sets both to zero, so call `os.stat()` itself. Store the identity as text: SQLite integers are signed 64-bit, POSIX inode numbers are unsigned 64-bit, and Windows file IDs are 128-bit ([`FILE_ID_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)).
- **Cloud placeholders, without downloading them.**
  - **Windows** ([file attribute constants](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants)): `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` (0x00400000) means reading the data fetches it from remote storage. `FILE_ATTRIBUTE_RECALL_ON_OPEN` (0x00040000) appears only in directory enumeration, so read `st_file_attributes` from `os.scandir()` entries. `FILE_ATTRIBUTE_OFFLINE` (0x00001000) means the data is not immediately available.
  - **macOS:** `SF_DATALESS` is 0x40000000 in `st_flags` ([`bsd/sys/stat.h`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stat.h)). Python exposes [`stat.SF_DATALESS`](https://docs.python.org/3/library/stat.html#stat.SF_DATALESS) only from 3.13, so the backend uses the number. The kernel also defines an I/O policy, `IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES` set to `IOPOL_MATERIALIZE_DATALESS_FILES_OFF`, that refuses to download dataless files ([`bsd/sys/resource.h`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/resource.h)). Test it before relying on it.
- **Ignore rules:** `fnmatch` from the standard library for SurfSense's own defaults. Add [`pathspec`](https://pypi.org/project/pathspec/) (MPL-2.0, 1.1.1) only if users' own ignore files are read.
- **Cases to handle and test:** Windows paths longer than `MAX_PATH`, Unicode normalisation differences in macOS file names, renames that change only letter case, and symlinks or junctions pointing outside the folder.

## Undo, later

- Before the agent changes a file, copy it into app data. Claude Code works this way ([checkpointing](https://code.claude.com/docs/en/checkpointing)):
  - it snapshots files before each prompt;
  - it keeps the 100 most recent checkpoints in a session;
  - it deletes a session's snapshots about 30 days after the session last saved one;
  - it does not track changes made by shell commands.
- Copy with `shutil.copy2` into a store keyed by content hash.

## Git, later

[`dulwich`](https://pypi.org/project/dulwich/) (1.2.15, Apache-2.0 or GPL-2.0-or-later) is the candidate for optional history. Confirm that it can keep the repository outside the user's folder before choosing it. opencode's own snapshots need a git repository inside the folder, and they are off ([`03-opencode.md`](03-opencode.md)).

## Open questions

- How linked folders and uploads live side by side, and whether uploads get folders inside the app (the `folder_id` gap).
- What a linked source shows when its folder is unavailable, such as a removable or network drive.
- How long the first scan and ingest take on a large folder, and whether either is limited.
- Where the watcher runs. Ingest has its own queue and worker ([ADR 0008](../../adr/0008-two-job-queues.md)).
- Whether cloud placeholders are skipped, listed as unavailable, or downloaded after the user agrees.
