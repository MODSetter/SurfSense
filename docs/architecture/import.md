# Import from SurfSense cloud

The desktop app imports the bundle the hosted service exports ([contract 3](../contracts/03-export-bundle.md)): every workspace, every ready document as markdown, the folder structure and the chat threads. The request validates the bundle and creates the workspaces; the documents then go through the ordinary upload path in the background and are indexed by the existing ingest task, so an imported document is an ordinary local document. Only markdown travels: original uploads and generated artifacts stay behind, and nothing touches the network.

**Code:** [`surfsense_local/backend/modules/migration/`](../../surfsense_local/backend/modules/migration/), [`surfsense_local/frontend/src/features/migration/`](../../surfsense_local/frontend/src/features/migration/)
**Decisions:** [ADR 0022](../adr/0022-markdown-only-cloud-import.md)

## The request

`POST /migration/import` is the module's only route. It takes the ZIP as a multipart upload and answers `202` with `ImportAccepted`: the local `id`, `cloud_id` and `name` of every workspace in the bundle. Before answering it:

1. Streams the upload into `imports/` under the data directory through `stream_upload()`, the function document uploads use, so the 500 MB upload cap applies to the bundle too and a larger one is refused with 413.
2. Reads the ZIP's directory, before extracting anything, and refuses more than 250,000 entries or more than 5 GiB unpacked with 413. These are import's own zip-bomb limits, sized far above any real account: the upload path's 10,000-entry archive limit is too small once OKF adds an `index.md` and a `log.md` per folder.
3. Parses `manifest.json`. `format` must be exactly `surfsense-export/1`; a workspace's `chats` must be `workspaces/<id>/chats.json`; a document `path` must start with `workspaces/<id>/documents/`, end in `.md`, and contain no backslash and no `..` segment. A bad manifest, a missing one, or a file that is not a ZIP is refused with 422, and the staged file is deleted. The manifest decides which members get opened, so this is the trust boundary; nothing else in the ZIP is read, the OKF `index.md` and `log.md` files included.
4. Finds or creates one local workspace per exported workspace, keyed by `cloud_id`, and commits them.

## The background job

The rest runs as a FastAPI `BackgroundTasks` job in the API process, with its own session, not on the Huey queue. For every document the manifest lists:

- The member streams into the workspace directory through `stream_upload()`, which hashes it on the way, and `validate_upload()` checks the bytes are UTF-8 text. A file that fails is skipped with a warning in the log.
- A document in the same workspace with that hash as its `dedup_key` means it was already imported, and the new copy is dropped.
- Otherwise it becomes a `FILE` document with the original, unsanitised title, and the file is stored under that title plus its extension, made safe as an upload's name is ([documents](documents.md#upload)). The bundle's own disambiguated name, such as `Notes_2.md`, is not kept. `document_metadata` carries `folder_path` (the directory under `documents/`), `source` (the hosted `DocumentType`, kept as an opaque label) and `cloud: {workspace_id, document_id}`, beside the usual `mime_type`, `size_bytes` and `suffix`.
- The file moves into the document's directory, the row commits, and the existing `ingest_document` task goes on the ingest queue.

The local schema has no folder table, so the hierarchy is kept as data. Markdown is in `TEXT_SUFFIXES`, so ingest reads the file directly and never starts Docling: an import is chunking and embedding only. The staged bundle is deleted when the job ends.

Threads from `chats.json` become ordinary local threads. Each message is stored as `{"text": ..., "citations": []}`, and a message that carried citation titles gains `\n\nSources: A, B`. Local citations point at chunks and imported ones have none, so they become text rather than dead chips.
The hosted thread id is kept as `cloud_id`. A thread already carrying that id
is left exactly as it is; a missing one and all of its messages are created.

## Running it again

Re-importing a bundle is safe for documents and threads. The workspaces are
found by `cloud_id`, every document whose `dedup_key` is already there is
skipped, and every thread whose `cloud_id` is already there is skipped. Running
an interrupted import again therefore fills the missing documents and threads;
documents already enqueued wait on the persistent queue. A thread renamed
locally keeps that name, while a thread newly present in a later export is
added. A re-export after document edits lands each edited document as a second
copy, not an update.

App versions before this database migration imported threads without retaining
their hosted ids. On upgrade, a workspace with a user message carrying the
importer's `citations` key is marked as containing that history, and
later imports leave all of its threads untouched rather than guessing identity
from titles or messages. To import newer hosted threads into one of those
workspaces, delete the workspace and import its bundle afresh, or reconcile the
histories manually.

A workspace containing only locally created turns is not marked, so those
turns do not prevent a re-import from recovering missing hosted threads.

## Entry points

- Settings › General › Import from SurfSense cloud. Its tooltip says workspaces, folders and chats come with it, documents come in as text and are indexed after import, and original files and generated artifacts stay in the cloud. Its link opens `https://surfsense.com/sunset` in the browser.
- The No workspaces screen. The API creates a workspace at startup whenever none exists, so this screen is rarely seen.

After the 202 the dashboard reloads its workspaces and opens the first imported one. `tests/integration/migration/test_import.py` runs the route against the zipped [`export-sample/`](../contracts/export-sample/) fixture.

## Known gaps

- There is no summary or progress endpoint: the button reads "Importing…" only while the upload is in flight, and after the 202 each document's own ingest status is the only progress.
