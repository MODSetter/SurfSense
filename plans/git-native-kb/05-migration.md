# Phase 5 — Migration

> After Phases 1–4. One-time, per-workspace, behind the flag. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

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

1. `app/knowledge_store/migrate.py` — `migrate_workspace(workspace_id)`: build the tree
   from `folders`/`documents` using the **same path/filename rules** as the live write
   path (`path_resolver` helpers; git path = virtual path minus `/documents`; see C1),
   one seed commit, preserve `unique_identifier_hash`.
2. Parity check: per-document byte/hash comparison (git blob vs Postgres markdown) +
   missing/extra path detection. Report, don't fix.
3. Seed adoption: record the seed revision as the indexer's last-indexed point (C7 —
   coordinate the bookkeeping shape with Phase 4's `index_revision`).
4. Per-workspace flag flip with a guard (refuse to flip if parity fails).
5. Dry-run mode (build repo, report parity diffs, flip nothing).

## Tests

- Seed is idempotent: re-running on an unchanged workspace records nothing.
- Parity: byte-identical workspace passes; one altered/missing/extra document fails
  with the offending paths named.
- `unique_identifier_hash` mapping preserved (connector docs still resolve).
- Adopted seed: `index_revision` on the first post-seed revision touches only that
  revision's changed paths (no workspace-wide re-embed).
- Dry-run flips nothing; failed parity blocks the flip.

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
