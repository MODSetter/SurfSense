# Runtime — results

> Owns: `surfsense_local/backend/modules/plugins/results.py`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Process: [`01-process.md`](01-process.md).

## Goal

After the plugin process exits, the results file becomes notes and run rows. The plugin did its own HTTP and already had its secrets. This stream does not talk to it.

## Work

- Read the results path the process stream passes in. Import runs on `succeeded`, `failed`, and `cancelled`. A missing file imports nothing.
- Each line is one JSON object. A line over 1 MiB, or a line that is not JSON, is skipped and a line is appended to `log_tail`. The other lines are still imported.
- `kind: "document"` with `title` and `content`: insert a `Document` the same way `create_note` does (`NOTE`, `pending`), set `document_metadata` to `pluginId`, `entry`, `runId`, commit, call `ingest_document`. Do not set `dedup_key`. A second identical line inserts a second note.
- Any other kind: insert `plugin_results` (`run_id`, `kind`, `body` JSON). Hand-written migration.
- Do not open a connection to the plugin's hosts. Consent for them is checked before the run starts ([`../app/01-api.md`](../app/01-api.md)); this module does not call `egress.require`.

## Acceptance

- A results file with one `document` line: a `NOTE` exists in the workspace and `ingest_document` was enqueued.
- Two identical `document` lines: two notes.
- A `kind` of `widget`: a `plugin_results` row, and no document.
- A file whose middle line is not JSON: the lines around it are imported, and `log_tail` mentions the skipped line.
- A plugin that performs HTTP during the run is not observed by this module. A test plugin can hit a local server; this module's code path does not connect to it.

## Needs from

[`01-process.md`](01-process.md) for the results path and the run row. The documents module, which already exists.
