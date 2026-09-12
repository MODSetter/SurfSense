# Contract 3: export bundle

One ZIP carrying a user's whole hosted account to the local app: every workspace, every ready document as markdown, folder structure, and chat threads. Markdown only: original uploads, generated artifacts, tool calls, agent steps, and live citation links do not travel. The export UI, the `/sunset` page, and the import summary all say so.

## Layout

```
manifest.json
workspaces/<workspace_id>/documents/<folder path>/<file>.md
workspaces/<workspace_id>/documents/**/index.md      (OKF, ignored by import)
workspaces/<workspace_id>/documents/**/log.md        (OKF, ignored by import)
workspaces/<workspace_id>/chats.json
```

**The manifest is the source of truth.** Import opens only the paths the manifest lists. Everything else in the ZIP is ignored, which keeps the bundle a valid OKF tree for other tools while import stays deterministic.

## `manifest.json`

```json
{
  "format": "surfsense-export/1",
  "exported_at": "2026-09-10T08:00:00+00:00",
  "workspaces": [
    {
      "id": 12,
      "name": "Research",
      "created_at": "2026-01-15T10:00:00+00:00",
      "chats": "workspaces/12/chats.json",
      "documents": [
        {
          "id": 301,
          "path": "workspaces/12/documents/Research/AI/Notes.md",
          "title": "Notes",
          "source": "FILE",
          "created_at": "2026-05-01T09:00:00+00:00"
        }
      ],
      "skipped": [
        {"id": 305, "title": "Draft", "reason": "processing"}
      ]
    }
  ]
}
```

| Field | Rules |
|---|---|
| `format` | Exactly `surfsense-export/1`. Import rejects any other value. Bumped only by a change to this file. |
| `exported_at`, `created_at` | ISO 8601 with UTC offset, as the exporter's `isoformat()` already emits. |
| `id` | Hosted integer ids, for `document_metadata.cloud` on the local side. Never reused as local ids. |
| `name`, `title` | Original strings, unsanitised. The sanitised form is in `path`. |
| `path` | Forward slashes, relative to the ZIP root, always under `workspaces/<id>/documents/`. |
| `source` | The hosted `DocumentType` value verbatim (`FILE`, `SLACK_CONNECTOR`, `NOTION_CONNECTOR`, ...). Opaque label; import stores and displays it, never switches on it. |
| `chats` | Always present, even when the file is `[]`. |
| `skipped` | Documents the exporter could not include, with `reason` in `pending`, `processing`, `empty`. Always present, possibly `[]`. |

## Document files

What `surfsense_backend/app/services/export_service.py` already writes: an OKF concept, i.e. YAML frontmatter (`type`, optional `resource`, `title`, `description`, `tags`, `timestamp`) followed by the markdown body. Titles are sanitised to 80 characters, allowing alphanumerics, space, `-`, `_`, `.`; collisions in one directory get `_2`, `_3`; a document titled `index` or `log` becomes `index_.md` / `log_.md`. Unicode letters survive sanitisation.

Import keeps the frontmatter in the stored file. It is a few lines and carries useful context.

## `chats.json`

```json
[
  {
    "id": 501,
    "title": "Comparing the two papers",
    "created_at": "2026-06-02T14:00:00+00:00",
    "messages": [
      {"role": "user", "text": "...", "citations": [], "created_at": "..."},
      {"role": "assistant", "text": "...", "citations": [{"title": "Notes"}], "created_at": "..."}
    ]
  }
]
```

- `role` is `user` or `assistant`. System, tool, and step messages are dropped.
- `text` is plain markdown with every hosted citation marker **removed** by the exporter.
- `citations` is `[{"title": ...}]`, distinct titles in first-seen order. It carries no chunk or document ids.

Import stores each message as `{"text": text, "citations": []}`, appending `\n\nSources: A, B` to assistant text when `citations` is non-empty. Local citations are chunk-backed and clickable; imported ones cannot be, so they become text rather than dead chips.

## Producer rules (Dev B)

- One bundle for the whole account, all workspaces, streamed synchronously as today.
- Every listed `path` exists in the ZIP; every `.md` under `documents/` that is not `index.md`/`log.md` is listed.
- `manifest.json` is the first entry in the ZIP so a streaming reader can find it without reading to the end.
- Regenerate `export-sample/` from a seeded account once the real exporter runs, and diff against the committed fixture.

## Consumer rules (Dev A)

- Reject `format` other than `surfsense-export/1`.
- **Path validation is a trust boundary.** Reject any `path` or `chats` that is absolute, contains `..` or a backslash, or does not start with `workspaces/<that workspace's id>/documents/` (or equals its `chats` entry). Reject before extracting anything.
- Cap ZIP entries and unpacked size with import-specific limits; the upload limits in `documents/storage.py` (10,000 entries) are too small for a large account once OKF index/log files are counted.
- Write each document through the existing upload path so it gets a content-hash `dedup_key`; store `folder_path` (directory part of `path` under `documents/`), `source`, and `cloud: {workspace_id, document_id}` in `document_metadata`.
- Re-importing the same bundle is a no-op per document via `dedup_key`. A re-export after edits lands as a second copy, not an update; acceptable for a one-shot migration.

## Fixture

`export-sample/` covers: two workspaces (one nested, one empty); a title collision (`Notes.md`, `Notes_2.md`); a document titled `index` (`index_.md`); a Unicode title; OKF `index.md`/`log.md` files that import must skip; one skipped document; one thread with a citation and one without. `python3 check-export-sample.py` validates the manifest against the tree with no dependencies.

## Tests each side owns

- Dev B: the exporter's output passes `check-export-sample.py`; a pending document appears in `skipped`, not `documents`; a message with three citation markers exports with none and three titles.
- Dev A: the zipped fixture imports to two workspaces, five documents, two threads; `index.md` and `log.md` are not documents; a manifest with `../` is rejected before any file is written; importing twice yields no new rows.
