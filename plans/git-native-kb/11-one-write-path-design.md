# Phase 11 — One Write Path: design & execution

**Status:** Design. Supersedes the terse "D — one writer, one allocator" bullet in
[`10-ingest-index-atomicity.md`](10-ingest-index-atomicity.md); that item is
re-scoped here after inspecting the code and the Phase 5 cut constraints.
**Umbrella:** [`00-umbrella-plan.md`](00-umbrella-plan.md).

## 0. Why this doc exists

D touches the whole write surface. Before changing it we map the pieces — every
store, every fact and who owns it, the one service where git and Postgres meet
(path allocation), and the order writes must happen in — so we make the write path
*reliable by construction*, not "write loosely and let a sweep clean up". Ground
truth is from code inspection (write paths, identity hashing, legacy writers, plan
intent), not memory; file:line evidence is inline.

(We used a components-and-ownership lens to *find* the pieces below; the names in
**bold** — Store, Projection, Reconciler, converge, writers — are the ones we keep
and use in code. No framework or pattern jargon is implied.)

## 1. Reality check: the plan status is stale

`05-migration.md:3` says *"No production workspace flipped yet."* This is wrong on
the ground: workspaces 30298 / 36723 / 33674 … are flipped and we have been
seeding/healing them. **Implication:** the "legacy vs git-native coexist behind a
flag" assumption is live, and any writer that ignores the flag is producing
git↔Postgres drift on already-flipped workspaces *right now*. That, not
`kb_persistence`, is the bleeding edge.

## 2. The pieces and who owns what

### 2.1 Stores and responsibilities

| Store / layer | Role | Backed by | Rule |
|---|---|---|---|
| **Store** | Write side for body + structure | per-workspace git repo; the file at a `/documents/**` path | one path ⇒ one file; single-writer (Redis write lock) |
| **Projection** | Read side, derived index | PG `documents` / `chunks` / `folders` | one-way `git → PG`; the derived index (chunks/embeddings) is fully rebuildable via `index_tree` |
| **Identity/Metadata** | Facts git cannot carry (yet) | PG `documents` columns: `document_type`, `document_metadata`, `unique_identifier_hash` | authoritative in PG until front-matter-in-git (deferred); **not** rebuildable from git alone |
| **Legacy PG write side** | *Deprecated* writer | `kb_persistence`, direct-PG connectors, dual-write processors | valid **only** on unflipped workspaces; deleted at the Phase 5 cut |

It is **not** "git owns everything, PG is a pure projection." While front-matter
stays in PG, ownership is **split** and the **path is the single join key** that
ties a git file to its PG row:

### 2.2 Ownership — who is authoritative for each fact

| Fact | Owner | Why / note |
|---|---|---|
| document **body** | **git** | files are diffs; the agent greps/reads them |
| folder **structure** | **git** | path segments + `.keep` markers |
| **path** (the join key) | **git owns**, **PG mirrors** (marker + column) | a file *is* its path; PG needs the mirror to join |
| **type, metadata, dedup-key** (`unique_identifier_hash`) | **PG** | git carries no front-matter in this phase, so these live only in PG |
| **title** (display name) | **PG** | shown in the sidebar; independent of the filename. The coupling is one-directional by design: an explicit editor title-edit renames the file (title→path via `save_document`+`title_is_explicit`), but a file move (agent `move_file`) never renames the title (path↛title) — so a reindex can't clobber a curated title. Consequence: an agent-driven rename changes the filename, not the sidebar label. |
| chunks, embeddings, `source_markdown` cache | **PG, derived** | rebuildable from git via `index_tree` |

The consequence that drives §4: PG holds authoritative facts git does not
(identity/metadata), so a write is inherently a **two-store write**. That is why
"git-first" is true for the *body* but identity is necessarily **PG-first**.

### 2.3 What we store

- **Workspace** — the consistency boundary: single-writer via the Redis write lock.
  Carries its write side (`knowledge_store_enabled`: legacy | git) and the
  projection high-water mark (`last_indexed_revision`).
- **Document** — its **identity in the store is its path** (a file is its path).
  Holds: body (git), type/metadata/dedup-key (PG), and a **lifecycle**:
  `pending → ready → failed`. A document is only *in the store* once it has a
  committed body; a `pending`/`failed` row legitimately has **no git file** and is
  therefore **not drift**.
- **Path** — `/documents/**.md`. The join key; the stable identity of a file.
  Owned by git, mirrored to PG.
- **Revision** — a git commit hash. `stamp` = last projected revision.
- **Chunk / Embedding** — derived, projection only; rebuildable.

### 2.4 Two identity regimes (the distinction the old doc missed)

`unique_identifier_hash = sha256(type : unique_id : workspace_id)`
(`document_hashing.py:6-18`). The `unique_id` differs by regime:

- **Source-identified** (upload, connectors): `unique_id` = the **stable source
  id**. The key is independent of path and is **deliberately not rewritten on
  move** (`rows.py:139-146`). Path is a *placement* of a stably-identified thing →
  the Reconciler can re-attach by dedup-key.
- **Path-identified / native** (NOTE, artifact): `unique_id` = the **virtual path**
  (`rows.py:84-93`), so identity *is* the path and a move **rewrites** the key
  (`follow_rename`, `rows.py:136-146`). The Reconciler re-attaches by
  path/marker/title, not by key.

This is why the Reconciler (§3) needs two modes, and why "re-attach by identity"
is precise only for source-identified docs.

### 2.5 The one legitimate flow

```
Writer → commit → revision           (Store.revise / _commit_files)
       → enqueue_index(workspace)     (index/queue.py)
       → converge git→PG              (index_changes / index_tree; stamp advances)
```

A writer that emits PG rows/chunks *without* going through commit + converge is
outside this flow. Class-B/C writers (§6) do exactly that — they are the drift
factory.

## 3. The Reconciler — path allocation as the git↔PG join

Path allocation is **not a util**; it is the one service where the git tree and PG
identity meet to decide, or re-find, a path. Everything hinges on it:
**a document must have exactly one path, identical in git and PG.** Break that and
you get the ` (2)…(n)` forks and orphans we see in prod.

### 3.1 Contract

`place(document, *, taken) -> Path`, always called **under the workspace write
lock**, where **`taken` is the git tree at HEAD and nothing else**. It is
**deterministic** and **idempotent by identity**:

1. If the row already records a path (the durable **column** first, the legacy
   marker only as a fallback — `recorded_virtual_path`) → **reuse it**.
2. Else if the doc is **source-identified** and a row/file already exists for its
   **dedup-key** → **reuse that path** (re-attach, never re-author).
3. Else **author** a fresh path: `allocate_path(name=title, folder_parts,
   taken=git@HEAD)`, breaking a clash with ` (n)` (`paths/naming.py:69-98`).

Re-run under any caller (live re-sync, re-seed, heal) lands on the **same** path.

### 3.2 Why `taken` must be the git tree only

`taken` is the occupancy set the allocator dodges when authoring a name. Today
there are two occupancy sources, and that split is the bug:

- **Runtime** reads the **git tree** — "the one authority on which files exist"
  (`service.py:281-299`).
- **Seeder** (`migrate_workspace`) starts `taken` **empty** and fills it **only
  from PG-recorded paths** (`migrate.py:199,209-223`) — blind to files git already
  holds (orphans, or live-authored files whose marker didn't persist). So it
  re-authors a name git already owns → forks.

PG's recorded paths are a **stale mirror**; git is where files actually collide.
One reconciler, one `taken` = git@HEAD, removes this class.

### 3.3 Current allocation sites (evidence they are not single-homed)

| # | Site | `taken` source | Evidence |
|---|---|---|---|
| 1 | `_author_path` (live) | git tree | `service.py:302-323` |
| 2 | `_place_unmarked` probe | **empty** | `service.py:336-340` |
| 3 | `save_document` | git minus own | `service.py:412-415` |
| 4 | `ingest_documents` | git full tree | `service.py:453-468` |
| 5 | `_relocation_of` (move) | git minus movers | `service.py:907-914` |
| 6 | **seeder** | **PG recorded paths only** | `migrate.py:218-223` |
| 7 | artifacts | **PG + working copy** | `artifacts:121-145` |

Two divergences motivated D1. (b) **recorded-path precedence** is now unified:
runtime and seeder both read the durable column first via `recorded_virtual_path`
(D1a). (a) **`taken` authority** still differs by site (git vs PG vs
PG+working-copy) — D1b unified only the two live incremental writers
(`save_document`, `ingest_documents`) onto the shared decision; the seeder,
artifacts and `_relocation_of` keep their own shape by design (see §8.2 for why).

## 4. Write ordering & durability

We cannot 2PC git and PG. So instead of hoping, we pick an ordering where **every
authoritative fact is made durable before the step that depends on it**, leaving
only a **re-derivable link** able to lag. That is the reliability guarantee — not a
background sweep.

### 4.1 When each fact becomes durable

| Fact | Owner | Made durable |
|---|---|---|
| identity, type, metadata, dedup-key | PG | **before git** (the `pending` row) |
| body | git | the git commit |
| **path link** (marker + column) | PG | **after** the git commit |

### 4.2 The canonical pipeline

```
Under the workspace write lock:
1. PG  mint/lookup identity → row(type, metadata, dedup-key)   [pending]   ← PG-first (git can't hold it)
2. body ready?  no → stay pending (NOT drift)                              ← lifecycle
3. Reconciler.place(doc, taken=git@HEAD) → path                            ← the join decision, made once
4. git commit body at path → revision                                     ← body-first for content
5. PG record path (marker + column), same task txn                        ← ONLY after step 4
6. enqueue converge → git→PG chunks                                        ← projection (async)
```

**Crash semantics — the only inconsistency possible is re-derivable:**

- Die between 4 and 5 → git file + PG row both exist (row from step 1), only the
  **link** is missing. Next touch or converge re-attaches by dedup-key
  (source-identified) or path (note). **Lossless, deterministic, no fork** (Reconciler §3.1.2).
- Die between 1 and 4 → `pending` row, no file → **not drift**; completed when the
  body arrives; if it never does, a `failed` row is excluded from the desired set.
- **Never possible:** "PG claims a path with no git file" — step 5 runs only after
  step 4. That is the one unhealable direction, and the ordering forbids it.

### 4.3 How atomic this actually is (honest)

- **This phase (front-matter in PG):** *atomic-for-correctness*. The two-store
  residue is only the path link, which is re-derivable, so no data is lost and
  content never diverges. Effectively atomic for the facts that matter.
- **Later phase (front-matter in git):** front-matter moves into the file, PG
  becomes a **pure projection** with zero independent authoritative facts, and the
  git commit becomes the **single atomic act**. That is literal atomicity — and it
  is the deferred OKF-as-stored-truth work (`00-umbrella-plan.md`), not this phase.

### 4.4 Writer-reliable, healer-insurance

Reliability comes from the **single reconciling writer**: after a successful write
task, git and PG agree — full stop. "Healing" (the drift monitor / `index_tree`)
is **not** the consistency mechanism; it is insurance for exactly two things:

1. **Process death mid-write** — the one moment step 5 can't cover; recovery is the
   lossless, deterministic re-attach above.
2. **Pre-existing legacy drift** — created by the *old* dual-writers (§6). A
   one-time migration, not a steady-state flow.

**Success criterion:** on a flipped workspace, steady-state drift **trends to
zero**. Any nonzero drift after the writers are unified is a **bug to fix**, not an
accepted "eventually consistent" flow.

## 5. Projection — simple verbs

Converge consumes a revision (or the whole tree) and applies, **keyed by path**,
three idempotent verbs:

- `upsert(path, body)` — create/attach the row, (re)build its chunks.
- `delete(path)` — remove the row when its file is gone.
- `rename(from, to)` — move the row, rewriting a note's path-based dedup-key.

The join is `resolve(path)`, re-attaching in order: **marker → dedup-key → path
column → title** (`paths/resolve.py`). Flow: an index request → apply verbs over
the revision delta (`index_changes`) or the full tree (`index_tree`) → advance
`stamp`. Idempotent and rebuildable: wiping PG and running `index_tree` restores the
projection exactly.

## 6. Writers — what actually stores today (verified)

An earlier draft over-counted writers. Verified against the dispatch, the index
route, and the two frozensets in `mcp_oauth/registry.py:254-288`: **a connector
stores to the KB only if it is neither LIVE nor DEPRECATED.**

- `LIVE_CONNECTOR_TYPES` — Slack, Teams, Linear, Jira, ClickUp, Calendar (+Composio),
  Airtable, Gmail (+Composio), Discord, Luma, **and now Notion + Confluence**.
  Real-time MCP/agent tools; **never stored**. Index route returns early
  (`search_source_connectors_routes.py:922`); scheduler auto-disables them
  (`schedule_checker_task.py:78-85`).
- `DEPRECATED_INDEXING_CONNECTOR_TYPES` — **GitHub, BookStack, Elasticsearch,
  Circleback(-connector)**. Ingestion retired; index route returns early (`:935`),
  scheduler disables.

So every `*_indexer.py` that still calls `safe_set_chunks` (slack, discord, teams,
luma, clickup, airtable, linear, github, bookstack, elasticsearch) is **dead code** —
no live caller reaches it. That is Phase-5 cleanup (delete), **not** a live drift
source. This is the correction: the old "Class B — bypass connectors" don't run.

### 6.1 The real writer set (each must follow §4.2)

| Writer | Trigger | Mechanism | Flipped status |
|---|---|---|---|
| File upload | `documents_routes` | indexing_pipeline (file_upload_adapter) | git-native ✓ |
| Editor / notes | `notes_routes` | `save_document` | git-native ✓ |
| Obsidian | plugin route | obsidian_plugin_indexer | git-native ✓ (kept per registry note) |
| Google Drive (native + Composio) | task/route | `index_unless_store_owns` | git-native ✓ |
| OneDrive | task/route | onedrive `kb_sync_service` | git-native ✓ |
| Dropbox | task/route | dropbox `kb_sync_service` | git-native ✓ |
| Local folder | route | `index_unless_store_owns` | git-native ✓ |
| Agent end-of-turn | chat | `kb_persistence` → `GitTreeBackend` | git-native ✓ (staging empties when flipped) |
| Artifacts | agent | git | git-native ✓ |
| **Extension** (web clips) | `documents_routes.py:127` | `safe_set_chunks` **+** `record_prepared_documents` (`extension_processor.py:139,155,169`) | **DUAL-WRITE → leaks** |
| **Circleback** (meeting notes) | `circleback_webhook_route.py:287` | `safe_set_chunks` **+** `record_prepared_documents` (`circleback_processor.py:202,216`) | **DUAL-WRITE → leaks** |

**Extension and circleback are the only live leak sources.** They chunk PG
unconditionally *and* record to git, so on a flipped workspace converge re-chunks
the git file → double chunks / race. Both fire **outside** the connector gate
(extension API, circleback webhook), which is why the LIVE/DEPRECATED sets don't
catch them. That — not the dead connector indexers — is the whole of D2.

```
 WRITERS                              GATE                    STORE (git = truth)         PROJECTION (PG, derived)
 =======                              ====                    ===================         ========================

 Agent end-of-turn ──GitTreeBackend───────────────────────▶  [ workspace git repo ] ─┐
 File upload ───────┐                                                                  │
 Editor / notes ────┤                                                          commit  ▼
 Obsidian ──────────┼─▶ knowledge_store_enabled_for? ──flipped──▶ [ git repo ] ──▶ converge ──▶ [ documents ]
 GDrive/OneDrive/   │        │                                                                   [ chunks    ]
   Dropbox/local ───┤        │                                                                   [ folders   ]
 Artifacts ─────────┘        └─unflipped──▶ legacy PG (direct chunk+embed) ──────────────────────────┤ (OK: unflipped only)
                                                                                                     │
 Extension ─────┐  ── PG chunks (safe_set_chunks) ──▶ legacy PG ═════════════════════════════════════╡ ◀─ LEAK on flipped
 Circleback ────┘        └─ AND record_prepared ──▶ [ git repo ] ──▶ converge ──▶ … (re-chunks) ──────┘    (double chunks / race)

 Dead (never reached): slack, teams, linear, jira, clickup, airtable, discord, luma, notion,
 confluence  [LIVE]  ·  github, bookstack, elasticsearch, circleback-connector  [DEPRECATED]
```

Legend: `──▶` legitimate flow (ends in a projected PG row via a git commit);
`══▶` illegitimate flow (PG chunks with no matching git-derived projection).

> Scope note: LIVE connectors that keep **connector-authoritative rows outside
> `/documents/**`** (if any remain) stay PG-owned and unpruned (`10-…:69`) — the fix
> for those is "don't let convergence treat them as drift," not "route through git."
>
> The periodic indexers above are git-native; but the **agent create-file tools**
> (`services/*/kb_sync_service.py::sync_after_create`, wired from
> `subagents/connectors/*/tools/create_file.py`) do write a `/documents` body PG-only
> via `safe_set_chunks` in real time. For KB connectors (Drive, OneDrive, Dropbox) the
> git-native periodic indexer reconciles that row by identical `unique_identifier_hash`
> (`prepare_for_indexing`'s existing-row branch), so it earns a git path on the next
> sync — a transient window, not permanent drift (whether converge then double-chunks
> the `safe_set_chunks` bytes is the same open check as the D2 leak below). For non-KB
> connectors it stays PG-only until the cut removes them. Same removal target, not a
> separate reroute.

## 7. Phase 5 cut alignment — safe now vs deferred

The cut deletes the legacy arm and is gated on **full fleet verification**
(`03-…:14`, `09-…:142`, `00-…:200`). We are mid-fleet. Therefore:

**Safe to do now** (additive, reduces live drift, reversible, flag-gated):
- **D1** — the Reconciler (§3): one `place()`, `taken`=git@HEAD, one recorded-path
  precedence, idempotent by identity. Pure consolidation.
- **D2** — bring the two live dual-write processors (**extension, circleback**) onto
  the §4.2 pipeline: on a flipped workspace defer chunking (`index_unless_store_owns`)
  instead of `safe_set_chunks`, so converge is the only chunker. Unflipped behavior
  untouched. (The dead connector indexers need no routing — they never run.)

**Deferred to the Phase 5 cut** (do **not** do now):
- Deleting `kb_persistence`, `KBPostgresBackend`, `revert_service`,
  `document_versioning`, revision models/tables, `paths/legacy.py`.
- `record_*` → intent-verb rename and the unconditional git-first facade (`09-…:142`).
- Front-matter-in-git (§4.3), which is what finally makes PG a pure projection.

### 7.1 Cutover sequence (two deployments, no maintenance window)

Deleting the legacy arm while any workspace is still unflipped (its documents are
served by that arm), or before extension/circleback defer chunking, would cause
silent data loss, so deletion is a **second, later deployment** — never bundled with
the fixes.

**Deploy 1 — all fixes, fully flag-gated (this branch):**
1. Land **D1** (Reconciler) and **D2** (extension + circleback on the §4.2 pipeline
   for flipped workspaces). Unflipped behavior byte-identical to today.
2. Born-flipped signup is already in (`users.py::create_default_workspace`,
   `workspaces_routes.py`). Ship it here.
3. Deploy. **No maintenance window / no registration freeze:** born-flipped means
   the unflipped set can no longer grow — it is frozen the moment Deploy 1 is live.
   (Guard: verify there is no third `Workspace(...)` creation path that skips the
   flag; only the two above are known.)

**Migration — operational, against Deploy-1 code, at any pace:**
4. Seed → verify byte parity → flip the frozen backlog (documents-bearing
   workspaces need parity; empty ones flip trivially). Resolve mismatched/failed
   docs rather than flipping over them. A workspace mid-migration is still
   unflipped and safely served by the legacy arm that Deploy 1 kept.
5. Confirm the fleet is 100% flipped **and** verified.

**Deploy 2 — the cut (pure subtraction):**
6. Delete the legacy arm, **drop the legacy tables**, do the `record_*`→intent verb
   rename. No behavior change — Deploy 1 already moved all live behavior to the
   git-first pipeline; this only removes the now-dead fallback. Safe only after 1–5.

Bottom line: **Deploy 1 makes git the sole write path for flipped workspaces
without removing the fallback; the migration flips the frozen backlog with no
downtime; Deploy 2 removes the unused fallback and its tables.**

### 7.2 Lean Coolify runbook (concrete)

1. **Deploy the new image to all services at once** — avoid a lingering old/new
   split (marker-stamping writers racing column-only ones).
2. **Migrate once** — `alembic upgrade head` as a single pre-deploy/release
   command, not per-replica start (N replicas racing `alembic upgrade` collide on
   the version table). Runs `189` (path backfill).
3. **Born-flipped signup is live** — the unflipped set is now frozen; it can only
   shrink.
4. **Seed the frozen backlog in batches** — `python -m scripts.migrate_knowledge_store
   --yes --workspace … --out reports.jsonl` (services up, one-off exec). This is the
   PG→git write that authors every body-bearing doc a file and records its `path`;
   parity per workspace lands in the JSONL. Dry-run first (drop `--yes`) to preview.
   Resolve any `mismatched`/`error` row here, while nothing is flipped yet. **Do
   not skip to flip:** a bare flip on an unseeded workspace serves PG-only bodies
   with no git file, and the drift sweep's whole-tree reindex then prunes them —
   the ws1 data-loss path.
5. **Flip the seeded batches** — `python -m scripts.migrate_knowledge_store --yes
   --flip --workspace …`. The re-seed is an idempotent no-op on a clean batch;
   `_set_flip` fires only on a passing parity report and carries the store head as
   `last_indexed_revision` (a NULL stamp would re-embed the whole tree). Watch drift
   between batches; roll one back with `--unflip --workspace …` if needed.
6. **Soak** — monitor the drift traces a few days. `missing` whose docs are non-KB
   connector types is a known scope false positive (the desired set counts every
   body-bearing row); it is closed at Deploy-2, not chased now.
7. **Cutover (Deploy-2)** — delete the legacy PG-only writers, stop dual-read, drop
   the marker column. Only after the fleet is 100% flipped and clean.

Why 4 and 5 are separate even though `--flip` already seeds-then-flips per
workspace: the split gives one fleet-wide checkpoint. Seeding is the heavy,
irreversible PG→git write; flipping is a flag. Seeding the whole batch first and
reading the aggregate JSONL lets a bad workspace be fixed before *any* flip, rather
than discovering it half-way through a combined pass.

## 8. Execution plan (smallest blast radius first)

Each step is strict TDD: a failing integration test that reproduces the leak/fork
on a flipped workspace, then the fix, no mocking of internal components.

1. **D1a — one recorded-path precedence.** Seeder reads marker→column like runtime.
   *Check:* a row whose marker and column disagree pins the **same** path under both
   re-sync and re-seed.
2. **D1b — one placement decision for the live writers (done).**
   `_reattach_or_author_path` (re-attach by identity → author) is the single
   decision `save_document` and `ingest_documents` now share; recorded-path reuse
   stays in each caller (the record-world check). The editor re-save re-attaches to
   a row's stranded git file instead of forking `name (2).md` — the twin of the
   existing ingest re-attach — proven by
   `test_a_resave_of_an_unmarked_row_reattaches_instead_of_forking`.
   Seeder, artifacts and `_relocation_of` are deliberately **not** folded: only an
   incremental writer of an *existing* row can hit the recordless-but-file-still-in-git
   fork. The seeder is a full-tree reconciler (empty `taken` + orphan removal) whose
   shape is correct and would regress under a git@HEAD `taken`; artifacts author a
   *new* row with no file to re-attach to; `_relocation_of` early-returns without a
   record. Folding them fixes no observed bug and adds risk. (Artifacts' PG+working-copy
   `taken` is a separate occupancy question, revisited only if it is shown to fork.)
3. **D2 — dual-write processors (extension, circleback).** On a flipped workspace
   they stop calling `safe_set_chunks` and instead defer chunking to converge (the
   Class-A `index_unless_store_owns` pattern); unflipped keeps `safe_set_chunks`.
   *Check:* on a flipped workspace, one extension/circleback ingest yields exactly
   one set of chunks (no double), with a git file present; unflipped unchanged.
4. **Cut (deferred):** delete the dead connector indexers
   (slack/discord/teams/luma/clickup/airtable/linear/github/bookstack/elasticsearch
   `safe_set_chunks` bodies), the legacy arm, verb rename, front-matter-in-git —
   tracked for Phase 5, not in this branch.

## 9. Invariants to preserve (regression guards)

- Path-only uniqueness: identical content at two paths ⇒ two rows
  (`test_duplicate_content_convergence.py`).
- One path per document, identical in git and PG (the Reconciler guarantee).
- One-way derivation: no step introduces a PG→git write (except the seeder, once).
- Rebuildability: after any step, `index_tree` still heals a wiped projection.
- Durability ordering (§4.2): no writer records a path before its git commit.
- Single-writer: all git writes stay under the workspace write lock.
- `document_type` preserved on upsert (no demoting ARTIFACT→NOTE).
- Unflipped workspaces: behavior byte-identical to today (all changes gated).

## 10. Out of scope

- `kb_persistence`/versioning/`paths.legacy` deletion and verb rename (Phase 5 cut).
- Deleting the dead connector indexers (LIVE + DEPRECATED `safe_set_chunks` bodies:
  slack/discord/teams/luma/clickup/airtable/linear/github/bookstack/elasticsearch) —
  Phase-5 cleanup; they never run, so not a drift source.
- Deleting the dead 1-phase upload chain (`process_file_upload` task with no dispatcher,
  `download_and_process_file` with no caller, `process_file_in_background`,
  `save_file_document`) — unreachable; the live upload path is 2-phase git
  (`process_file_upload_with_document`). Deletable at the cut with the connector bodies.
- Front-matter-in-git / OKF-as-stored-truth (the phase after this one).
- Legacy report/Typst demolition (`10-…:68`).
- Connector-authoritative non-`/documents` rows staying PG-owned (`10-…:69`).
- Drift-monitor fan-out / visibility-timeout redesign (tracked separately).
