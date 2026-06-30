# Subplan 01 — Rename foundation (DB)

Part of [00-umbrella-plan.md](00-umbrella-plan.md), Phase 1. Backend only (`surfsense_backend`).

> **Status: SHIPPED** · as of 2026-06-27 · branch `feat/rename-searchspace-to-workspace` · PR [#1546](https://github.com/MODSetter/SurfSense/pull/1546)
> Last commit of this phase: `49d3001fb` (DB rename through migration 170). Phase 1 + Phase 2 shipped as one atomic PR.
> The sections below are the **original design/rationale**; the as-built state + how to re-verify live in the [Implementation record](#implementation-record-as-built) at the bottom. Ground truth for files/commits is the PR, not this doc.

## Goal

Physically rename the `SearchSpace` schema to `WorkSpace` in PostgreSQL via a single Alembic migration, and update the ORM's physical mapping + the Zero publication so the app keeps booting and running — WITHOUT yet touching the ~250 backend files that reference the `search_space_id` Python attribute (that symbolic rename is Phase 2).

Canonical target names:

- Table `searchspaces` -> `workspaces`
- Tables `search_space_roles` / `search_space_memberships` / `search_space_invites` -> `workspace_roles` / `workspace_memberships` / `workspace_invites`
- Column `search_space_id` -> `workspace_id` (all child tables); `external_chat_accounts.owner_search_space_id` -> `owner_workspace_id`
- Named constraints/indexes containing `searchspace` -> `workspace` (see inventory)

## The central coupling decision (read first)

A physical column rename instantly breaks every line of code that reads the old name. Today that is large:

- `search_space_id` / `searchspaces` appear in ~250 backend files outside `db.py` (Grep over `surfsense_backend/app`, excluding `db.py`). Almost all are Python ORM attribute reads like `Document.search_space_id` or `.search_space_id`.

To keep Phase 1 self-contained and low-risk, decouple the PHYSICAL rename from the SYMBOLIC rename using an explicit column-name mapping shim:

- Keep the Python attribute name `search_space_id`, but bind it to the new physical column:
  - Today: `search_space_id = Column(Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), ...)` ([surfsense_backend/app/db.py](surfsense_backend/app/db.py) line 1382 etc.)
  - Phase 1: `search_space_id = Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), ...)`
- Result: the physical DB is fully renamed, the ORM maps the unchanged Python attribute to the new column, and the ~250 callers keep working untouched.
- Phase 2 then renames the Python attribute (`search_space_id` -> `workspace_id`), the class (`SearchSpace` -> `Workspace`), schemas, routes/API, and drops the explicit `"workspace_id"` first-arg shim.

CONFIRMED: ship the shim approach. (Alternative big-bang rename rejected as too risky.)

## Current-state inventory (all citations from code)

### The table itself

- `class SearchSpace(... __tablename__ = "searchspaces")` — [surfsense_backend/app/db.py](surfsense_backend/app/db.py) line 1688.

### Child tables with a `search_space_id` FK to `searchspaces.id`

All declared `ForeignKey("searchspaces.id", ondelete="CASCADE")` unless noted. Locations in [surfsense_backend/app/db.py](surfsense_backend/app/db.py):

- `new_chat_threads` (605), `external_chat_bindings` (897), `token_usage` (1113), `folders` (1318), `documents` (1382), `video_presentations` (1506), `reports` (1533), `connections` (1561, nullable), `image_generations` (1672), `search_source_connectors` (1878), `logs` (1905), `search_space_roles` (2045), `search_space_memberships` (2076), `search_space_invites` (2118), `prompts` (2176), `agent_action_log` (2495), `document_revisions` (2566), `folder_revisions` (2607), `agent_permission_rules` (2643).
- `external_chat_accounts.owner_search_space_id` (785-786, nullable) — note the distinct column name.

In other model modules:

- `document_files` — [surfsense_backend/app/file_storage/persistence/models.py](surfsense_backend/app/file_storage/persistence/models.py) line 32.
- `automations` — [surfsense_backend/app/automations/persistence/models/automation.py](surfsense_backend/app/automations/persistence/models/automation.py) line 27.
- `notifications` — [surfsense_backend/app/notifications/persistence/models.py](surfsense_backend/app/notifications/persistence/models.py) line 50.
- `podcasts` — [surfsense_backend/app/podcasts/persistence/models.py](surfsense_backend/app/podcasts/persistence/models.py) line 71.

### Named constraints / indexes that embed the old name

- `uq_searchspace_user_connector_type_name` on `search_source_connectors` — [db.py](surfsense_backend/app/db.py) line 1831.
- `uq_searchspace_role_name` on `search_space_roles` — line 2032.
- `uq_user_searchspace_membership` on `search_space_memberships` — line 2069.
- `idx_documents_search_space_id` and `idx_documents_search_space_updated` (raw `CREATE INDEX CONCURRENTLY` DDL in a module-level list) — lines 2821-2830.
- `ix_external_chat_bindings_search_space_state` — line 978-979.

These reference `search_space_id` by COLUMN but the index/constraint NAME does not embed "searchspace" (definitions auto-follow a column rename; names can stay):

- `ix_notifications_user_space_created` — [notifications/persistence/models.py](surfsense_backend/app/notifications/persistence/models.py) line 36-41.
- `uq_agent_permission_rules_scope` — [db.py](surfsense_backend/app/db.py) line 2680.

### CHECK constraint referencing the column AND a scope literal

- `ck_connections_scope_owner` on `connections` — [db.py](surfsense_backend/app/db.py) lines 1578-1584:
  - `"(scope = 'GLOBAL' AND search_space_id IS NULL ...) OR (scope = 'SEARCH_SPACE' AND search_space_id IS NOT NULL ...) OR (scope = 'USER' ...)"`.
  - The physical CHECK expression auto-follows a column rename (Postgres tracks by attnum), but the model's `CheckConstraint(...)` text must be updated to `workspace_id` for create_all/autogenerate consistency.
  - The scope string literal `'SEARCH_SPACE'` is a `ConnectionScope` value, not a column — see Confirmed decisions.

### Zero publication (single source of truth)

- [surfsense_backend/app/zero_publication.py](surfsense_backend/app/zero_publication.py) is "the single source of truth for `zero_publication`" (module docstring, lines 1-11). Publication changes "should update `ZERO_PUBLICATION` and call `apply_publication()` from a migration" (lines 3-5).
- `search_space_id` appears in **four** published column lists (a recent `main` merge added the `automations`/`new_chat_threads` entries — previously only `documents`/`podcasts`):
  - `DOCUMENT_COLS` line 31.
  - `AUTOMATION_COLS` line 57 (`["id", "search_space_id"]`).
  - `NEW_CHAT_THREAD_COLS` line 62 (`["id", "search_space_id"]`).
  - `PODCAST_COLS` line 76.
  - (`AUTOMATION_RUN_COLS` lines 44-53 does **not** contain the column — `automation_runs` is scoped via `automation_id`, so it auto-follows and needs no edit.)
- These are the only **four** published tables with column lists that include the column (`ZERO_PUBLICATION` map, lines 81-94; other entries are `None` = all columns and auto-follow). All four (`documents`/`automations`/`new_chat_threads`/`podcasts`) columns must be updated to `workspace_id`, then `apply_publication(op.get_bind())` re-run.
- Reconcile pattern to copy: [surfsense_backend/alembic/versions/155_reconcile_zero_publication.py](surfsense_backend/alembic/versions/155_reconcile_zero_publication.py) (calls `apply_publication(op.get_bind())`, no-op downgrade).

## Migration design

### Conventions (from the repo)

- Revision ids are plain integers; the new migration chains after the **then-current head** — verify with `alembic heads` at implementation time, since the head advances as other PRs merge. As of the latest `main` sync the head is `169` ([surfsense_backend/alembic/versions/169_migrate_google_oauth_account_ids_to_sub.py](surfsense_backend/alembic/versions/169_migrate_google_oauth_account_ids_to_sub.py); chain `166→167→168→169`), so the new file would be `170_rename_searchspace_to_workspace.py` with `revision="170"`, `down_revision="169"`. (Note: Phase 4b and Phase 5 each add a migration too; whichever lands first takes the next integer — chain by actual head, not by these illustrative numbers.)
- Migrations run one-per-transaction under an advisory lock — [surfsense_backend/alembic/env.py](surfsense_backend/alembic/env.py) lines 77, 80-95. So all renames below land atomically.
- Raw `op.execute("ALTER TABLE ...")` is the house style (e.g. [165_add_chunk_position.py](surfsense_backend/alembic/versions/165_add_chunk_position.py) lines 39-49).

### upgrade() steps (order matters)

1. Rename tables:
   - `ALTER TABLE searchspaces RENAME TO workspaces;`
   - `ALTER TABLE search_space_roles RENAME TO workspace_roles;`
   - `ALTER TABLE search_space_memberships RENAME TO workspace_memberships;`
   - `ALTER TABLE search_space_invites RENAME TO workspace_invites;`
   - FKs and PKs follow the table automatically (referenced by OID). Sequence `searchspaces_id_seq` and `*_pkey` keep old names — CONFIRMED: also `ALTER SEQUENCE searchspaces_id_seq RENAME TO workspaces_id_seq;` and `ALTER INDEX searchspaces_pkey RENAME TO workspaces_pkey;` (plus the RBAC tables' `*_id_seq` / `*_pkey`) for a clean final schema.
2. Rename columns on every child table (use `ALTER TABLE <t> RENAME COLUMN search_space_id TO workspace_id;` for the full list in the inventory; plus `external_chat_accounts.owner_search_space_id -> owner_workspace_id`).
   - Metadata-only, fast even on large tables (same property the repo relies on in [165](surfsense_backend/alembic/versions/165_add_chunk_position.py) lines 36-41).
   - ORDERING NOTE: the RBAC tables were renamed in step 1, so their column rename must target the NEW table names (`workspace_roles` / `workspace_memberships` / `workspace_invites`), not the old ones.
3. Rename the named constraints/indexes. Use defensive/idempotent forms because some objects are created at runtime, not by migrations (see review finding 4):
   - Constraints (no `IF EXISTS` for `RENAME CONSTRAINT`; wrap each in a guarded `DO` block that checks `pg_constraint`):
     - `uq_searchspace_user_connector_type_name` -> `uq_workspace_user_connector_type_name` (on `search_source_connectors`).
     - `uq_searchspace_role_name` -> `uq_workspace_role_name` (on `workspace_roles`).
     - `uq_user_searchspace_membership` -> `uq_user_workspace_membership` (on `workspace_memberships`).
   - Indexes (these two are created by the runtime `setup_indexes()` startup routine, NOT a migration, so they may or may not exist depending on `DB_BOOTSTRAP_ON_STARTUP`; use `IF EXISTS`):
     - `ALTER INDEX IF EXISTS idx_documents_search_space_id RENAME TO idx_documents_workspace_id;`
     - `ALTER INDEX IF EXISTS idx_documents_search_space_updated RENAME TO idx_documents_workspace_updated;`
     - `ALTER INDEX IF EXISTS ix_external_chat_bindings_search_space_state RENAME TO ix_external_chat_bindings_workspace_state;`
4. Zero publication. DECISION: we will recreate the Zero replication (reset the zero-cache replica) as part of this deploy, so consumer recovery is handled out-of-band and finding 3 is de-risked. Follow the repo's established publication patterns — do NOT use raw `DROP`/`CREATE PUBLICATION` (forbidden by [116_create_zero_publication.py](surfsense_backend/alembic/versions/116_create_zero_publication.py) lines 8-17; reintroduces bug #1355). Sequence inside the migration:
   - (Safe ordering) Neutralize the column-list dependency surgically so the RENAME is unconditionally permitted: `ALTER PUBLICATION zero_publication DROP TABLE documents, automations, new_chat_threads, podcasts;` (all **four** column-list tables). This removes ONLY their column-list dependency and is far safer than re-emitting the whole member set via `SET TABLE` (which is a full replacement and would drop any table accidentally omitted from the hand-written list, including the quoted `"user"` table). `DROP TABLE` from a publication is within the blessed ALTER-PUBLICATION family — it is NOT the forbidden raw `DROP/CREATE PUBLICATION`.
   - Rename the columns (steps 1-2).
   - Update canonical `DOCUMENT_COLS`/`AUTOMATION_COLS`/`NEW_CHAT_THREAD_COLS`/`PODCAST_COLS` to `workspace_id` in [zero_publication.py](surfsense_backend/app/zero_publication.py) (31, 57, 62, 76), then call `apply_publication(op.get_bind())` (blessed plain `ALTER ... SET TABLE`, as used by [155_reconcile_zero_publication.py](surfsense_backend/alembic/versions/155_reconcile_zero_publication.py)) to re-add all four dropped tables with the narrowed `workspace_id` column lists and reconcile the full member set in one shot.
   - Reference template for forcing a schema-change event (only if event triggers are unavailable): the `COMMENT ON PUBLICATION` bookend trio in [143_force_zero_publication_resync.py](surfsense_backend/alembic/versions/143_force_zero_publication_resync.py) lines 104-137. With event triggers installed (current setup), `apply_publication` is sufficient.
   - Replica recreate (operational, out-of-band): reset the `surfsense-zero-cache` replica (delete the volume / rely on `ZERO_AUTO_RESET=true`) so zero-cache does a fresh initial sync from the corrected publication. This is the "recreate replication" step and the primary consumer-recovery mechanism.
   - INTERLOCK FOOTGUN (review finding 2): if any of the canonical `DOCUMENT_COLS`/`AUTOMATION_COLS`/`NEW_CHAT_THREAD_COLS`/`PODCAST_COLS` are NOT updated to `workspace_id` before `apply_publication` runs, `_format_table_entry` ([zero_publication.py](surfsense_backend/app/zero_publication.py) lines 148-149) silently DROPS the mismatched table(s) from the publication (no error). Gate with `--verify` (see Verification).
5. No DDL needed for the `ck_connections_scope_owner` CHECK: the physical expression auto-follows the column rename (Postgres tracks the column by attnum). The model's `CheckConstraint(...)` text is updated separately as an ORM edit (see ORM edits) so create_all/autogenerate stay consistent.

### downgrade()

Provide a full reverse (rename `workspaces` -> `searchspaces`, columns back, constraints/indexes back, then restore the OLD publication shape). Note the repo sometimes uses no-op downgrades for publication-only migrations ([155](surfsense_backend/alembic/versions/155_reconcile_zero_publication.py) lines 22-23), but a structural rename should be reversible.

CRITICAL (review finding 7 — do NOT call `apply_publication()` in downgrade): `apply_publication()` reads the LIVE canonical in `zero_publication.py`, which after this change is `workspace_id`. In a downgrade the column is back to `search_space_id`, so `apply_publication` would find `workspace_id` missing and silently DROP the four column-list tables (`documents`/`automations`/`new_chat_threads`/`podcasts`) from the publication — the finding-2 footgun, self-inflicted. Instead, the downgrade must restore the old shape with HARDCODED `search_space_id` column lists (for all four tables) via a plain `ALTER PUBLICATION ... SET TABLE`, mirroring the constants-style approach in [143_force_zero_publication_resync.py](surfsense_backend/alembic/versions/143_force_zero_publication_resync.py) (which embeds literal `DOCUMENT_COLS` rather than importing the live module). Use the same DROP-then-SET neutralize sequence in reverse.

COHERENCE (review finding 6): even with a correct downgrade SQL, `downgrade()` only produces a consistent RUNNING system if the PRIOR code revision is redeployed alongside it — under the shim the model maps the attribute to physical `workspace_id`, which no longer exists after a pure DB downgrade. Document rollback = revert code + schema together as one operation.

## ORM / source edits in this phase (mapping only)

These are required so the ORM matches the renamed physical schema; they are NOT the broad symbolic rename. Explicitly OUT of scope for Phase 1: relationship attribute names (`User.search_spaces`, `back_populates="search_space"`, etc.) and class names (`SearchSpace`, `SearchSpaceRole`, ...). They stay as-is here and are renamed in Phase 2 — leaving them untouched is what keeps the ~250 callers green.

1. [surfsense_backend/app/db.py](surfsense_backend/app/db.py):
   - `__tablename__` for `SearchSpace` (1688), `SearchSpaceRole` (2027), `SearchSpaceMembership` (2064), `SearchSpaceInvite` (2113) -> new table names.
   - Every `ForeignKey("searchspaces.id", ...)` -> `ForeignKey("workspaces.id", ...)`; `ForeignKey("search_space_roles.id"...)` -> `workspace_roles.id`; `ForeignKey("search_space_invites.id"...)` -> `workspace_invites.id`.
   - Apply the explicit-name shim on each `search_space_id` column: `Column("workspace_id", ...)`; and `owner_search_space_id = Column("owner_workspace_id", ...)`.
   - Update ONLY the `name=` kwarg of constraints/indexes (1831, 2032, 2069, and the Index at 978-979). CRITICAL (review finding 1): do NOT change the inner column-reference strings (`"search_space_id"` at 1827, 2030, 2068, 2674, 979) — under the shim the column's `.key` is still `search_space_id`, and declarative `__table_args__` resolves these strings against `Table.c` by `.key`. Changing them to `"workspace_id"` raises a config-time error and the app won't boot.
   - Update the runtime raw index DDL strings + names in `_INDEX_DEFINITIONS` (~2821-2831; +1 line vs the pre-merge cite after `main`'s `RefreshToken` edit — locate by grep): both the index name and the physical column (`search_space_id` -> `workspace_id`). These must match the migration's renamed indexes and ship in the same release; `setup_indexes()` ([db.py](surfsense_backend/app/db.py) ~line 2856) re-creates them under the new name on next boot when `DB_BOOTSTRAP_ON_STARTUP` is true.
   - Update `ck_connections_scope_owner` text (1579-1582) `search_space_id` -> `workspace_id`.
   - Update `ix_external_chat_bindings_search_space_state` name + the surrounding Index (978-979).
2. Module models — `__tablename__` unaffected, but apply the column shim + FK target string:
   - [file_storage/persistence/models.py](surfsense_backend/app/file_storage/persistence/models.py) (32), [automations/persistence/models/automation.py](surfsense_backend/app/automations/persistence/models/automation.py) (27), [notifications/persistence/models.py](surfsense_backend/app/notifications/persistence/models.py) (50, plus the index at 36-41), [podcasts/persistence/models.py](surfsense_backend/app/podcasts/persistence/models.py) (71).
3. [surfsense_backend/app/zero_publication.py](surfsense_backend/app/zero_publication.py): `DOCUMENT_COLS` (31), `AUTOMATION_COLS` (57), `NEW_CHAT_THREAD_COLS` (62), and `PODCAST_COLS` (76) `search_space_id` -> `workspace_id`. (The `_expected_columns` special-casing on line 118 keys off table names `{"documents","user","podcasts"}`, not the column, so no change there — and `automations`/`new_chat_threads` aren't in that `_0_version` allowlist anyway.)
4. Runtime raw-SQL audit (defensive): grep `surfsense_backend/app` for any `text(...)` / hardcoded `"searchspaces"` or `search_space_id` strings that execute at runtime (not Python attribute access) and fix them here, since the shim only covers ORM attribute access. Expectation is few; the ~250-file footprint is overwhelmingly attribute access handled by the shim.

## Confirmed decisions

- Strategy: SHIM approach (physical DB rename now; Python attribute kept via `Column("workspace_id", ...)`; symbolic attribute/class/API rename deferred to Phase 2).
- Scope literal `'SEARCH_SPACE'` (the `ConnectionScope` value in `ck_connections_scope_owner`): KEEP the string value as-is; only fix the `search_space_id` column reference in the CHECK. No enum change, no data UPDATE.
- Cosmetic names: RENAME auto-named sequences/PK indexes (`searchspaces_id_seq` -> `workspaces_id_seq`, `searchspaces_pkey` -> `workspaces_pkey`, and the RBAC tables' `*_id_seq`/`*_pkey`) for a clean final schema.
- Transition: HARD CUTOVER at the DB layer (no backward-compat old column/view). Client apps hit the API (Phase 2), not the DB, so the DB rename does not affect them. (Phase 2 RESOLVED: hard cutover, no API aliases — see [02-rename-backend.md](02-rename-backend.md).)
- Zero: RECREATE THE REPLICATION (reset the zero-cache replica / `ZERO_AUTO_RESET`) on deploy for consumer recovery. Publication mutated only via the blessed `apply_publication` / `ALTER ... SET TABLE` path (never raw DROP/CREATE PUBLICATION, per migration 116). See migration step 4.

## Release coupling (review finding 5)

The Alembic migration, the `db.py` edits (shim + constraint `name=` + `_INDEX_DEFINITIONS` + `ck_connections_scope_owner` text), the 4 module-model edits, and `zero_publication.py` MUST ship as ONE atomic release. There is no safe intermediate state where some are updated and others are not.

## Verification & rollout

- HARD GATE: `python -m app.zero_publication --verify` (CLI at [zero_publication.py](surfsense_backend/app/zero_publication.py) ~lines 266-269; `verify_publication` defined at ~203) must report verified, in CI and immediately post-migrate. This is the guard against the interlock footgun (finding 2).
- Boot the API + a Celery worker; run a smoke chat + a document upload to exercise `documents.workspace_id` and the publication; confirm Zero clients still sync `documents`/`podcasts`.
- AUTOGENERATE DRIFT CHECK (strong, cheap): after the change, `alembic revision --autogenerate` must produce an EMPTY diff. A non-empty diff means the ORM and migrated DB disagree — i.e. a missed `ForeignKey("searchspaces.id")` string, a constraint `name=` mismatch, or a forgotten `Column("workspace_id", ...)` shim. This single check catches most subtle misses.
- Confirm `alembic upgrade head` then `alembic downgrade -1` then `upgrade head` round-trips on a staging copy. NOTE: this validates SQL reversibility only — it is NOT an app-health check, because new code cannot run against the downgraded schema (finding 6). The downgraded intermediate state must show `documents`/`podcasts` still present in the publication with `search_space_id` lists (proves the hardcoded downgrade publication shape from finding 7 works).
- Run the full backend test suite; the shim keeps attribute-based tests green — watch specifically for fixtures/raw SQL that hardcode the table name `searchspaces`.
- Pre-flight check: confirm no DB views/materialized views depend on the renamed objects (they auto-follow a rename, but verify so a later `pg_dump` diff holds no surprises).
- Raw-SQL audit done-check: grep `surfsense_backend/app` for `text(...)` or string literals containing `searchspaces` / `search_space_id` that execute at runtime; current audit found none beyond ORM attribute/dict-key usage (which the shim covers).

## Risks (with review findings)

- RENAME COLUMN under an active Zero publication column list (finding 3) — de-risked: step 4 neutralizes the column-list dependency (publish documents/podcasts as ALL columns) before the rename, and the zero-cache replica is recreated on deploy, so consumers re-sync cleanly.
- Silent publication drop if canonical col lists aren't updated (finding 2) — mitigated by the `--verify` hard gate.
- Zero consumers recover via the planned replica recreate (reset `surfsense-zero-cache` / `ZERO_AUTO_RESET=true`), giving a fresh initial sync from the corrected publication; no raw DROP/CREATE PUBLICATION (bug #1355).
- Constraint/index column-ref strings accidentally changed under the shim (finding 1) — config-time boot failure; mitigated by the explicit "only change name=" instruction.
- Runtime-created indexes may not exist at migrate time (finding 4) — mitigated by `IF EXISTS` renames + guarded `DO` blocks for constraints.
- Missing a `ForeignKey("searchspaces.id")` string leaves SQLAlchemy metadata pointing at a non-existent table — fails fast at mapper config (`NoReferencedTableError`); the inventory list above is the checklist.
- Partial/non-atomic release (finding 5) or code-less downgrade (finding 6) — mitigated by shipping all edits in one release and treating rollback as code+schema together.
- `downgrade()` calling `apply_publication()` against the live (new) canonical (finding 7) — would silently re-drop `documents`/`podcasts`; mitigated by hardcoding the old `search_space_id` publication shape in `downgrade()` (143-style), never importing the live module.

## Out of scope (later phases)

- Phase 2: rename Python attribute `search_space_id` -> `workspace_id`, class `SearchSpace` -> `Workspace`, Pydantic schemas, API routes/paths (`/searchspaces` + `/search-spaces` -> `/workspaces`), Redis keys, storage path segments; drop the explicit `Column("workspace_id", ...)` shim.
- Frontend Zero schema, route segment, i18n — deferred frontend umbrella.

---

## Implementation record (as-built)

### Deviations from the plan

- **Migration 168 idempotency fixed up-front**: the plan flagged from-scratch alembic as pre-existing-broken; we made 168 idempotent so the rename starts from a clean head, but did **not** take on the full baseline-squash. From-scratch `alembic upgrade head` therefore stays pre-existing-broken (rev 23 conflict); only the existing-DB `169 -> 170` path is in scope/verified.
- **Cosmetic sequence/PK renames applied** (the plan's confirmed decision): `searchspaces_id_seq -> workspaces_id_seq`, `searchspaces_pkey -> workspaces_pkey`, plus the RBAC tables' `*_id_seq` / `*_pkey`, for a clean final schema.
- Everything else implemented exactly as designed: shim via `Column("workspace_id", ...)`; publication mutated **only** through the blessed `apply_publication` path (no raw DROP/CREATE PUBLICATION, per migration 116); `__table_args__` inner column-reference strings deliberately **left** as `search_space_id` (flipped in Phase 2).

### Carve-outs as-shipped (Phase 1)

- `'SEARCH_SPACE'` CHECK literal in `ck_connections_scope_owner` kept; only the `search_space_id` column reference flipped to `workspace_id`. No enum/data migration.

### Verify current state (re-runnable)

Each line is a command + the last captured result. Re-run to confirm the *current* truth instead of trusting the snapshot. Schema gates assume a DB at rev `170` (locally `surfsense_oldshape`) with `AUTH_TYPE=LOCAL` (so the env-gated `oauth_account` table isn't in the ORM metadata).

- **Schema drift (ORM ↔ physical @170)** —
  `AUTH_TYPE=LOCAL DATABASE_URL=postgresql+asyncpg://…@localhost:5432/surfsense_oldshape uv run alembic check`
  → last (2026-06-27): `No new upgrade operations detected.` (With `AUTH_TYPE=GOOGLE` the only delta is the env-gated `oauth_account` table — unrelated to the rename.)
- **Publication columns** —
  `rg -n 'workspace_id|search_space_id' app/zero_publication.py`
  → last (2026-06-27): all four lists = `workspace_id`, zero `search_space_id`.

Validated during the build run (2026-06-26), **not** reproducible on a `create_all`-built snapshot (it has no `zero_publication` object): `python -m app.zero_publication --verify` → verified (interlock-footgun guard, finding 2); `alembic upgrade 170 → downgrade -1 → upgrade 170` round-trip (SQL reversibility; downgrade restores the `search_space_id` publication shape via hardcoded lists, per finding 7).
