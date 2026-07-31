# Phase 5 — Migration

> **Status: TOOLING SHIPPED (2026-07-30); fleet flips pending.** Seeder (`app/knowledge_store/migrate.py`), fleet runner (`scripts/migrate_knowledge_store.py`), per-workspace flag (`workspaces.knowledge_store_enabled`), drift monitor. No production workspace flipped yet; cut-time deletion (versioning code + table drops) runs after fleet verification.
>
> After Phases 1–4. One-time, per-workspace, behind the flag. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
>
> **Executing it:** the ordered commands and checks for a production run live in [`05a-seed-runbook.md`](05a-seed-runbook.md) — merge, deploy, pre-flight, dry run, seed, verify, flip in batches, watch, roll back.

## Objective

Move each existing workspace's KB from Postgres-as-truth to git-as-truth by exporting current documents/folders into an initial git repo, then flipping `KNOWLEDGE_STORE_ENABLED` for that workspace once content identity is verified. **Adopt the existing derived index; never rebuild it during migration.**

## Why "adopt, don't rebuild" (amended 2026-07-29)

The first draft gated the flip on `seed → reindex() → compare search results`. A full
`reindex` re-chunks and re-embeds every document — the same cost class as the chunk-table
backfill we once measured at ~21 days and abandoned. It is also **unnecessary**: the seed
copies bytes *out of Postgres*, so the existing `chunks` rows and their vectors are already
the correct derived index of the seeded repo. Verifying bytes proves the index; rebuilding
it proves nothing extra and costs weeks plus embedding spend.

This is the standard online-migration shape (Stripe's dual-write → backfill → verify →
cutover → delete; expand/contract): Phase 3's flag-gated dual-run **is** the dual-write
step, the seed **is** the backfill, byte parity **is** the shadow-read verification, the
flag flip **is** the cutover, and the Phase-5 delete sweep **is** the contract.
Re-embedding is never on that path.

## Locked model

- **Seed commit per workspace.** Read current `folders` + `documents`
  (`source_markdown`/`content`) and write the real tree into the Phase-1 repo as **one
  seed commit** (`author=migration`), using the same path rules as the live write path
  (C1). Streamed table scan + file writes: O(documents) I/O, no embeddings, no locks on
  hot tables. Idempotent — re-seeding unchanged content is a no-op commit.
- **Preserve identity.** Keep the `unique_identifier_hash` ↔ path mapping so connector
  re-syncs and existing references stay stable.
- **Parity = byte identity, not reindex.** Gate the flip on: every seeded blob's bytes
  equal the document's Postgres markdown (and nothing is missing/extra). O(documents)
  hashing, seconds per workspace. `reindex()` stays a disaster-recovery tool; run it once
  on one small pilot workspace as a one-time Phase-4 sanity check, never as a
  per-workspace gate.
- **The seed revision is adopted, never incrementally indexed** (contract C7). To
  Phase 4's `index_revision`, the seed looks like "every file added" — feeding it through
  would re-embed the whole workspace (the storm the parity redesign exists to avoid). The
  seeder marks the seed revision as the indexer's starting point; incremental indexing
  begins with the first post-seed revision.
- **No span work in migration (amended 2026-07-29, second pass).** New chunks get
  `start_line`/`end_line` at cut time (nullable columns, instant ALTER — C2); legacy
  chunks stay `NULL`, render un-numbered, and cite at document level (fail-closed
  normalizer). Convergence is a **separate deadline-free daily fill job** — CPU-only,
  matching stored chunk texts against the git blob (post-flip truth; all-or-nothing per
  document, see C2), most-used workspaces first — that is operational work, never a
  migration step or flip gate. Migration
  itself touches the chunks table zero times; the mandatory-backfill mistake (PR #1523,
  the ~21-day job) stays dead.
- **Chunker drift converges lazily, on edit.** Migrated chunks were cut by whatever
  chunker was live at index time. Do not re-chunk them eagerly and do **not** warm the
  embedding cache from legacy rows (entries would be keyed under the current
  `chunker_version` for boundaries it did not produce — cache poisoning). On a document's
  next edit, the normal pipeline re-chunks it under the current version; the reconciler
  and the embedding cache bound the cost to what actually changed.
- **Rollback window.** Keep Postgres content intact until the flagged workspace is
  verified; flag flip is the point of no return per workspace.

## Work items

1. ✅ `app/knowledge_store/migrate.py` (2026-07-29) — `migrate_workspace(session, workspace_id)`:
   builds the tree from `documents` via the live path rules (`build_path_index` +
   `doc_to_virtual_path`, identical paths to every write path), falls back to `content`
   for rows predating `source_markdown`, one seed revision (`author=MIGRATION_IDENTITY`).
   The DB-free core `seed_workspace(workspace_id, files, dry_run=)` carries the tests.
   Seed = "make the tree exactly this": a catch-up re-seed also **removes** documents
   deleted in Postgres since the prior seed, so seed→(activity)→re-seed→flip converges.
   Unlike the recorder it does **not** guard on `KNOWLEDGE_STORE_ENABLED` — migration
   runs before the flip by definition.
2. ✅ Parity check (same run): content-address comparison via `list_paths` +
   `compute_content_id` — zero file reads — reporting `missing`/`extra`/`mismatched`;
   `MigrationReport.ok` is the flip guard's verdict. Report, don't fix.
3. ⏳ Seed adoption: the report surfaces `seeded_revision`; recording it as the
   indexer's last-indexed point is Phase 4's side of C7 (coordinate the bookkeeping
   shape with `index_revision`).
4. ✅ Per-workspace flag flip guarded by `report.ok` (2026-07-29) —
   `workspaces.knowledge_store_enabled` (migration 175, default false) AND the global
   `KNOWLEDGE_STORE_ENABLED` (kept as the master kill switch: env off = everything off,
   instantly). `knowledge_store_enabled_for(workspace_id)` resolves the pair (30s
   per-process cache on the workspace half). The agent factory resolves it **once per
   turn** and passes the verdict down (resolver, persistence middleware, compiled-graph
   cache key — the flag rotates cached graphs), so a turn never mixes write paths; the
   recorder and the disconnect safety-net check per call. The fleet runner flips:
   `--yes --flip` (only ever on a passing report), `--unflip --workspace N` rolls back.
   Flipping back loses nothing — Postgres is updated in both modes; git goes stale and
   a catch-up re-seed converges it.
5. ✅ Dry-run mode: skips the write, reports parity against head, creates nothing for
   fresh workspaces.
6. ✅ Fleet runner `scripts/migrate_knowledge_store.py`: dry-run by default, fresh
   session per workspace, append-only JSONL reports, non-zero exit on any not-ok.
7. ✅ Drift instrumentation (2026-07-29) — the coexistence window is watched, not
   trusted. Every recording attempt emits
   `surfsense.knowledge_store.record.outcome` (`flow` = editor_save / sync_batch /
   turn_commit; `status` = recorded / noop / failed): a non-zero `failed` rate means
   git is falling behind Postgres. A daily beat task (`check_knowledge_store_drift`,
   05:15) runs the seeder's dry-run parity over every **flipped** workspace and emits
   `surfsense.knowledge_store.drift.check` (ok / drift / error) per workspace, with a
   warning log naming the missing/extra/mismatched paths — the JSONL report as an
   always-on alarm instead of a by-hand check.

   **Amended 2026-07-30 — the monitor repairs, it does not just alarm.** Phase 4's
   hourly sweep compares a stored git revision against the store's HEAD, so *both*
   sides of its predicate come from git: it is structurally blind to drift that
   lives on the Postgres side, which is exactly what this check sees. Leaving that
   half to `reindex_knowledge_store.delay(...)` typed by hand contradicted Phase 4's
   own "runbook steps get forgotten; converging systems don't" — same class of
   fault, two different answers. A `drift` verdict now enqueues the whole-tree
   converge (`index_tree` upserts paths Postgres lacks, overwrites content that
   disagrees, prunes marked rows whose file is gone), capped at
   `REPAIR_ENQUEUE_CAP = 10` per run: fleet-wide drift is a systemic fault, and
   fanning out rebuilds would compound it. `error` stays alarm-only — a store the
   check could not read is not fixed by indexing it harder, and a failed report's
   parity fields describe nothing. Known ceiling, marked in the code: drift
   `index_tree` cannot fix (an unmarked Postgres row with no file in the tree, i.e.
   a writer bypassing git) costs one rebuild per run until a human intervenes; the
   alarm persists throughout, and the upgrade path is a per-workspace attempt count.

8. ⛔ **Blocks the flip — the UI delete never reaches git** (found 2026-07-31, local
   canary). `DELETE /documents/{id}` marks the row and hands off to
   `delete_document_task`, which has no store awareness: the row goes, the file stays.
   Four orphans in the canary workspace across two sessions — the normal outcome, not a
   race. This is the deferred REST adapter's missing half (ADR 0002): the agent's `rm`
   records a revision, the HTTP path does not. It also inverts item 7's repair loop.
   `index_tree` reads the surviving file as truth and re-creates a document the user
   deleted, and once it has, git and Postgres agree again, so the check reports `ok` on
   a workspace that just resurrected deleted content. Flip a real workspace before the
   delete path records a revision and user deletions come back on the next drift run.
   Any other HTTP write that bypasses the recorder has the same shape; auditing the
   route surface is part of the fix, not a follow-up to it. The audit found about
   twenty such writers, which turned the fix into its own phase —
   [`07-direct-caller-adapter.md`](07-direct-caller-adapter.md). The flip waits on it.

## Tests

- ✅ Seed records one revision, passes parity, migration-authored.
- ✅ Idempotent: re-seeding unchanged content records nothing.
- ✅ Parity names missing/extra/mismatched paths; drift fails `ok`.
- ✅ Dry-run builds nothing on fresh workspaces; passes parity on seeded ones.
- ⏳ `unique_identifier_hash` mapping preserved (connector docs still resolve) — needs a
  Postgres-backed test or the pilot dry run.
- ⏳ Adopted seed: `index_revision` on the first post-seed revision touches only that
  revision's changed paths (lands with Phase 4).

## Out of scope

- Binary re-import (blobs stay in the blob store).
- Frontend cutover (separate umbrella).
- Eager re-chunking of migrated content (lazy, on edit — see locked model).

## Open questions

1. Big-bang all-workspaces vs. staged per-workspace rollout order (recommend staged).

## Sources

- Stripe, "Online migrations at scale" — dual-write → backfill → verify reads → cut
  writes → delete old (https://stripe.com/blog/online-migrations).
- Expand/contract (parallel change) — old and new coexist through every step; never a
  breaking change in one step.
- Lazy backfill discipline — fill only when absent; never rewrite an existing value
  because derivation logic changed; pair lazy convergence with a bounded background job.
