# Phase 5 — Migration

> After Phases 1–4. One-time, per-workspace, behind the flag. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

## Objective

Move each existing workspace's KB from Postgres-as-truth to git-as-truth by exporting current documents/folders into an initial git repo, then flipping `KB_GIT_ENABLED` for that workspace once search parity is verified.

## Locked model

- **Seed commit per workspace.** Read current `folders` + `documents` (`source_markdown`/`content`) and write the real tree into the Phase-1 repo as **one seed commit** (`author=migration`).
- **Preserve identity.** Keep the `unique_identifier_hash` ↔ path mapping so connector re-syncs and existing references stay stable.
- **Verify before flip.** After seeding, run `reindex(workspace)` (Phase 4) and confirm the rebuilt chunk set reproduces pre-migration search behavior on a fixed query set.
- **Rollback window.** Keep Postgres content intact until the flagged workspace is verified; flag flip is the point of no return per workspace.

## Work items

1. `app/kb_git/migrate.py` — `migrate_workspace(workspace_id)`: build the tree from `folders`/`documents` using the **same path/filename rules** as the live write path (`path_resolver` helpers; git path = virtual path minus `/documents`; see [`00c-shared-contract.md`](00c-shared-contract.md) C1), write `Document.source_markdown`/`content` as each file, preserve `unique_identifier_hash`, one seed commit.
2. Parity check: seed → `reindex` → compare chunk counts and top-k search results against a captured pre-migration baseline.
3. Per-workspace flag flip with a guard (refuse to flip if parity check fails).
4. Dry-run mode (build repo, report diffs, do not flip).

## Tests

- Round-trip: a seeded workspace's `reindex` chunk set matches the pre-migration set for the same content.
- `unique_identifier_hash` mapping preserved (connector docs still resolve).
- Dry-run flips nothing; failed parity check blocks the flip.

## Out of scope

- Binary re-import (blobs stay in the blob store).
- Frontend cutover (separate umbrella).

## Open questions

1. Big-bang all-workspaces vs. staged per-workspace rollout order (recommend staged).
2. Baseline capture method for the parity check (fixed query fixtures vs. sampled).
