# Phase 8 — Store facade & path law

> **DESIGN (2026-07-31).** Facade already reshaped (`knowledge_store/service.py`);
> this phase locks the **path law** and the module shape around it, then makes the
> **Phase-5 seed the vehicle that heals every path** as it flips each workspace.
> Depends on Phases 3/4/6/7. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> **Prerequisite of the fleet seed** ([`05-migration.md`](05-migration.md), work item 1;
> [`05a-seed-runbook.md`](05a-seed-runbook.md)). Amends C1's filename rules
> ([`00c-shared-contract.md`](00c-shared-contract.md)).

## Objective

One law for how a folder or file is named, where it lives, and how a path resolves
back to a row — obeyed identically on **both sides** of the boundary: the git tree
(the truth) and the Postgres `documents`/`folders` rows (what the UI reads). Get it
wrong and the two representations fork: a path in git that no row answers, or two
rows claiming one path. That is the filesystem dying quietly.

The law lives in one robust submodule (`knowledge_store/paths/`), the way `index/`
and `schemas/` already do, and the **migration seed applies it per workspace** — so
the debt is fixed once, at flip, not lazily patched at twenty call sites forever.

## Why now

The path logic is the one piece still scattered and still carrying the virtual-FS
debt into the git era. Three concrete faults, each traced:

- **Split-brain identity.** References/mentions key on `Document.id` and render the
  path *live* (`references/documents/resolver.py`) — Notion's model. But store
  resolution keys on the **path**, baked into `unique_identifier_hash =
  hash(NOTE, virtual_path, ws)` — Obsidian's model. One half treats the path as
  disposable, the other as identity. That split is why a retitle drifts the hash and
  why Phase 4 needed the `RenameDetector` patch to stop id churn.
- **The join is an un-indexed JSON value.** A row records where its file lives in
  `document_metadata->>'virtual_path'` (`PATH_MARKER`). Git's tree *physically*
  cannot hold two files at one path; Postgres, with no constraint on that value,
  can — and `virtual_path_to_doc`'s marker lookup is a JSON scan, not an index hit.
- **`.xml` is load-bearing, by an accident we can now undo.** C1 kept `.xml`
  *only* to protect `unique_identifier_hash`. Demote that hash to a fallback (below)
  and the reason evaporates: git holds markdown, so the tree should say `.md`.
  The legacy ` (<doc_id>).xml` collision suffix is worse — it ties a path to a row
  id, the exact coupling the authored-once model removes.

## What we learned (before inventing)

Four systems solved path-vs-identity; two coherent models fall out.

| System | Identity anchor | Path/title role | Rename cost |
|---|---|---|---|
| Obsidian / Foam | the **path** | *is* identity; links store path strings | rewrite every inbound link; external rename breaks links |
| Notion | permanent **id** | display-only, disposable | free — references point at the id |
| Dendron | **id in frontmatter** | filename is a label; id survives manual/external moves | rewrites backlinks *and* keeps the id |
| Git itself | **content hash**; renames **not stored** | n/a | detected post-hoc by ≥50% similarity — *can be wrong* |

The lesson: **pick one model, make the other derived.** Our references are already
id-keyed and can't cheaply change, and git can't durably track a rename anyway (the
≥50% heuristic is what bit us on small edited notes). So the choice is forced:
**id is identity; the path is an authored-once label.** Dendron's in-file id is the
strongest form but changes file bytes (breaks the seed's byte-parity gate, C7) and
only pays off when a *non-SurfSense* process writes the repo — the deferred remote
feature. `ponytail:` frontmatter-id is YAGNI now; upgrade path = add `surfsense_id`
frontmatter when external git writers land, and normalize it out of the parity hash.

## Locked model — the path law

**Naming — decided once, at write time, into git.**

- A path is a validated `StorePath`: `/documents/<folders…>/<file>`. A foreign
  namespace, a `..`/`.`/empty segment **raises** (`StorePath.from_virtual`) — a
  silent mismatch forks one document into two identities across the boundary.
- Filename = `normalize_filename`: sanitize-once (invalid chars → `_`, collapse
  whitespace, cap 180), keep an author-given real extension, else default `.md`.
  **Idempotent** (`plan`→`plan.md`, `plan.md`→`plan.md`) — the property that lets
  any side re-derive the same name without disagreeing.
- Folder segment = `safe_folder_segment` (same sanitize, no extension).
- Collisions resolve **once** via `allocate_path` → ` (2)`, ` (3)` — **never** a
  doc id.
- Uploads: git holds the *extracted markdown*, so the tree name is
  `markdown_name_for_source` (`report.pdf`→`report.md`); the original filename stays
  in `document_files` for the download path.
- `.keep` is a **reserved name** — the folder keep-file (below). `allocate_path`
  never emits it and `StorePath` rejects a document authored at it, so a folder
  marker can never be mistaken for content.

**Folder law — folders start in the store, git or not.**

Every folder operation originates at the facade and projects to a `folders` row; no
caller writes a folder row by hand. Git cannot store an empty directory, which is the
*only* place folders need help — everywhere else a folder is just a path prefix.

- **Implied folders** exist because a document lives under them. Derived from
  document paths (`ensure_folder_hierarchy` today); no git object of their own. Delete
  the last document and the folder is gone — exactly git's behaviour.
- **Explicit / empty folders** are materialized by one **keep-file**,
  `documents/<folder>/.keep`, so the empty folder is a real path in git and survives
  commit, clone, and rebuild. The keep-file is engine-internal: filtered from every
  document listing and never projected as a `Document`, never shown to the agent or UI.
  Its presence carries intent — *this folder should exist even when empty*.
- **Facade verbs** (recorded as revisions, like file ops):
  `create_folder(path)` writes `path/.keep`; `remove_folder(path)` is one revision
  removing the whole subtree (documents + keep-files); `move_folder`/rename is one
  revision moving every descendant via `tx.move`, so document ids survive (Phase 7's
  "a folder op is one revision over every descendant").
- **Projection derives `folders` rows** from the union of (document parent paths) ∪
  (folders holding a `.keep`), and **prunes** a row that has neither a document nor a
  keep-file. This closes the Phase-6 gap (an emptied folder was never pruned and
  `folder_deleted` never fired): an implied folder vanishes with its last document; an
  explicit one keeps its `.keep` and persists.

`ponytail:` a keep-file left in a folder that later gains documents is redundant but
harmless; the folder simply stays explicit. Upgrade path = a sweep dropping keep-files
from non-empty folders if the clutter ever matters.

**The join — git and Postgres in lockstep.**

- **Git tree is the authority; rows are its projection.** Postgres never *derives* a
  path from a title (that re-derivation is the legacy bug). The row carries the git
  path **verbatim**, and its `folder_id` chain **mirrors** the git folder segments
  (`ensure_folder_hierarchy`), so the path the UI shows *is* the git store path —
  round-trip identity, not a second opinion.
- **Postgres gets git's structural guarantee.** Promote the path off the JSON marker
  onto a real `documents.path` column with a **partial unique index on
  `(workspace_id, path)`** — Postgres finally unable to hold two rows at one path,
  the same invariant the tree enforces for free. `virtual_path_to_doc` collapses to
  one indexed lookup, legacy fallbacks only for unhealed rows.
- References/mentions store the **id**, render the path live. No path string is ever
  a foreign key — that is what keeps renames free (no Obsidian-style link rewrite).

**Backward compatibility — read tolerant, write canonical.**

- Unflipped workspaces keep the quarantined legacy `doc_to_virtual_path` derivation
  (`kb_postgres`) — production untouched until its own flip.
- The resolver tolerates **both** spellings: authored-once `.md` and legacy
  `.xml`/` (<doc_id>).xml`. Old chat text and connector titles keep resolving.
- `unique_identifier_hash` **demotes** from primary resolver to a fallback; the path
  column is the identity. This retires the hash-drift hazard the `.xml` rule existed
  to avoid, which is what makes `.md` safe.

**Healing — lazy, and finished by the seed.**

- The path column starts **nullable**. It is written through at every natural
  touchpoint — the projection's row upsert, and the service layer's save/move — so a
  flagged workspace heals as it is used. No big-bang backfill; nothing rewrites an
  existing value because derivation changed (the lazy-backfill discipline in
  [`05-migration.md`](05-migration.md) sources).
- **The seed is the closing move.** The migration seed already rewrites each
  workspace's whole tree "to exactly this"; teach it the new naming rules and it
  re-authors every path canonically in one deterministic pass — `.xml`→`.md`,
  id-suffix collisions → ` (2)` resolved by **`created_at` then `id`** (stable, one
  time), recording the chosen path on each row. A workspace crosses the flip already
  healed; there is no per-workspace debt left to chase.
- The unique index is created **concurrently, after** enough rows carry a path to
  build clean — deferred so it never blocks writes (a partial index
  `WHERE path IS NOT NULL` skips the unhealed tail).

## Module shape — `knowledge_store/paths/`

`paths.py` today mixes four concerns; split it into a package so the legacy quarantine
is literally the file you delete at the Phase-5 cut:

| File | Holds | Load-bearing rule |
|---|---|---|
| `paths/store_path.py` | `StorePath`, `StorePathError`, `DOCUMENTS_ROOT`, segment validation | the value every boundary constructs and then trusts |
| `paths/naming.py` | `normalize_filename`, `safe_folder_segment`, `markdown_name_for_source`, `allocate_path` | authoring rules — the only place a fresh name is chosen |
| `paths/layout.py` | `workspace_store_path`, working-copy roots | on-disk layout; stays free of `app.db` (imported on the enqueue path) |
| `paths/resolve.py` | `virtual_path_to_doc`, `_resolve_by_title`, `_resolve_folder_id` | reverse resolution, path column first |
| `paths/legacy.py` | `safe_filename` (`.xml`), `doc_to_virtual_path`, `PathIndex`, `parse_doc_id_suffix`, `build_path_index`, `virtual_path_of` | `kb_postgres` renderers only — **deleted at the cut** |

`paths/__init__.py` re-exports the public surface so callers import from
`app.knowledge_store.paths` and never reach a private symbol. An import-boundary test
(work item 5) pins that nothing under `app/` outside the module reaches path internals
or opens a `transaction`.

## Work items

Ordered so the tree is safe before the fleet touches it.

1. ✅ **Split `paths.py` into the `paths/` package** above; `__init__` re-exports the
   surface; legacy symbols isolated in `paths/legacy.py`.
2. ✅ **`documents.path` column + lazy healing.** Nullable column, write-through in
   `index/project.py` (row upsert) and `service.py` (save/move); `virtual_path_to_doc`
   reads the column first, marker/hash/title as fallbacks. Alembic (`177_add_documents_path`):
   instant `ADD COLUMN`, no backfill.
3. ✅ **Teach the seeder the naming law.** `migrate.py` authors paths via
   `allocate_path` (not `doc_to_virtual_path`), resolves collisions once by
   `created_at` then `id`, records the chosen path on each row, emits `.md`. Parity
   gate (C7) still byte-identity against Postgres markdown.
4. ⏳ **Partial unique index on `(workspace_id, path)`**, created concurrently after
   the fleet is healed (a runbook step, not a blocking migration).
5. ✅ **Guard test** — import boundary (nothing under `app/` outside the module
   reaches `Transaction`, engines, or path internals) + the round-trip symmetry test.
   The package root no longer re-exports `Transaction`, closing the last leak.
6. ✅ **Rewired importers** off the duplicate `agents/chat/runtime/path_resolver` module
   onto `app.knowledge_store.paths` (28 files, module-path swap) and deleted the 425-line
   duplicate — closing a layering inversion where `index/{converge,rows,project}` imported
   *up* into the agent runtime. The stripping `parse_documents_path` (the one behavioural
   difference: it strips `.xml`/`(id)` to form a title) moved to `paths/legacy.py` as the
   exported one; `store_path`'s raw splitter was unused and dropped. All 1310 knowledge_store,
   document_upload, middleware and agent tests green.
7. ✅ **Folder verbs on the facade** — `create_folder`, `remove_folder`, `move_folder`
   over the `.keep` materialization; `StorePath` reserves `.keep` so it is never a
   `Document`; folder ops are one revision each on the facade.

7a. ◐ **Route wiring (partial).** The document-move handlers (`PUT /documents/{id}/move`,
   `PUT /documents/bulk-move`) now call `record_moved_documents` after the `folder_id`
   change, so a flipped workspace's move reaches git and a rebuild finds the file at the
   new folder instead of resurrecting the old one; a no-op on an unflipped workspace
   since the verb self-guards.

7b. ✅ **Live write path authors `.md`.** The three facade writers that choose a name —
   `save_document`, `ingest_documents`, `move_documents` — now derive through the naming
   law (`allocate_path`/`normalize_filename`, `(2)` collisions) instead of the legacy
   `.xml` derivation, so a flipped workspace stops *creating* the debt the seed heals.
   Occupancy comes from the git tree (the authority on which files exist), and a row's own
   file is excluded so a lost-marker re-derivation cannot collide the document with itself.
   Switched together — a partial swap forks a doc between `.md` and `.xml` and breaks the
   no-op check. `doc_to_virtual_path`/`virtual_path_of` stay for the resolver and unflipped
   `kb_postgres`; only the flipped facade writes `.md`.
7c. ✅ **Unblocked folder-route prerequisites.** Both blockers on routing folder CRUD
   through the facade are cleared: `move_folder` now renames the row in place
   (`index/folders.py:reparent_folder`) before reconcile, so a rename/reparent keeps the
   folder id and its children ride along on `parent_id`; and the seed materializes each
   empty leaf folder as a `.keep` (`migrate.py:_empty_folder_keeps`), so a flipped
   workspace's whole-workspace reconcile no longer prunes pre-existing empty folders.
7d. ✅ **Routed folder CRUD/move through the facade.** `folders_routes` create, rename,
   move and delete now record to git after the row op, through thin module verbs
   (`record_created_folder`, `record_moved_folder`, `record_removed_folder`,
   `folder_virtual_path`) — routes never spell a path or bind a workspace. Rename/move
   capture the old path *before* mutating, then record the move; the in-place reparent
   no-ops (the row is already at its new name) and git still follows, id kept. Delete
   drops only the folder's `.keep` markers (`remove_folder_markers`), never its files:
   the incremental indexer prunes a row the moment its file leaves the tree, so removing
   documents here would race the purge task that owns their chunks and blobs. All verbs
   self-guard, so an unflipped workspace is untouched.
   **Still deferred:** making the projection the *sole* row writer (stripping creation
   from upload/notes/connectors) — the Phase-5 cut; unflipped prod still writes rows on
   those paths.
8. ✅ **Folder projection + prune** — `index/folders.py` derives `folders` rows from
   document paths ∪ keep-files and prunes rows with neither. Runs on every folder
   verb (immediate) and on the full rebuild (`index_tree`), closing the Phase-6 gap;
   the deleted row replicates to the UI via Zero. `ponytail:` a per-document delete
   still leaves an implied empty folder until the next full rebuild prunes it —
   matches how document prune already only runs on a full reconcile.

## Tests

- **Symmetry (the load-bearing one):** author a path → project to rows → the
  UI-rendered path **equals** the git store path (round-trip); two rows cannot claim
  one path (unique index); a collision is deterministic across repeated runs.
- `normalize_filename` is idempotent; `StorePath` rejects foreign namespace and
  traversal; `allocate_path` never emits a doc id.
- Resolver resolves both `.md` and legacy `.xml`/` (<id>).xml`; a healed row resolves
  by the path column in one query.
- **Folder law:** `create_folder` on an empty path survives a commit + fresh
  `index_tree` (the keep-file persists it); `.keep` never becomes a `Document`;
  removing the last document from an implied folder prunes its `folders` row and fires
  `folder_deleted`, while an explicit folder's row survives empty; a folder rename is
  one revision and keeps every descendant's id.
- Seeder re-authors an `.xml`/id-suffixed workspace to canonical `.md`, records the
  path, and re-seeding is a no-op (idempotent, per C7).
- Import-boundary test holds.

## Out of scope

- Frontmatter-id (deferred; upgrade path noted in the locked model).
- The read side over HTTP (rows still answer reads — umbrella "Deferred").
- Deleting `paths/legacy.py` and `kb_postgres` — that is the Phase-5 cut.

## Open questions

1. Whether the partial unique index waits for the whole fleet or lands per-workspace
   once a workspace is fully healed (favor fleet-wide, once, to avoid a half-built
   index racing an unhealed workspace).

## Sources

- Obsidian internal links / "shortest path" resolution; Notion data model (UUID as
  identity, title as display); Dendron frontmatter `id` (identity survives moves);
  Foam "decouple id from slug"; git rename detection (content similarity, ≥50%, no
  stored rename) — the four models the locked decision chose between.
- ADR 0002 — ports and adapters (the facade this path law sits behind).
- C1 (tree layout, filename rules — amended here), C2 (`unique_identifier_hash`
  demotion), C7 (seed byte parity, no re-index) — [`00c-shared-contract.md`](00c-shared-contract.md).
- Lazy-backfill discipline — [`05-migration.md`](05-migration.md) sources.
