# Phase 5a — Timeline (the moat asset)

> Part of **Phase 5 — Intelligence & Timeline**. Sibling: `05b-intelligence.md` (the process that writes
> this state). **Build first** within Phase 5 — the tables must exist before the hot loop writes them.
> **Depends on** `04a` (the verbs the loop calls) and Phase 1 (the DB / migration baseline).
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. The Timeline is **CI-owned, new tables** — it is **not**
> the Knowledge Base (documents/embeddings) and **not** `automation_runs`.

## Objective

Durably store the **time-shaped truth** for each Tracker. This is the asset: **time is the moat** —
accumulated history a later entrant cannot re-create. Design rule: **store deltas, not snapshots — no
change, no row.** Storage grows with the *rate of change*, not the number of runs.

## Current state (cited)

- **No CI state exists today** — crawled data is explicitly *not* indexed; the only persisted CI state is
  what this phase introduces.
- **Reference models** for shape/placement: connectors/folders ORM in `app/db.py` (full-row Zero
  publication, like folders/connectors); `automations`/`automation_runs` as the *orchestration* analog
  (this is the **fact** analog, deliberately separate).
- **Hot-loop pre-check** (`05b` step 2) reads `WebCrawlerConnector.format_to_structured_document(
  exclude_metadata=True)` to compute the `content_hash` stored here.

## Target design

### The state / process split

Intelligence (`05b`) is the only **writer** (via the hot loop). **Readers** — the Conversation domain
today, future dashboards/alerts/the deferred resale product — read the Timeline **directly, without
running the loop**. That separation is why Timeline is its own domain.

### The three stores

| Store | Role | Write pattern |
|-------|------|---------------|
| `tracked_entities` | stable identity per tracked thing (the Tracker's `identity_rule` → `entity_key`) | written **once** |
| `entity_current_state` | latest values + `content_hash` + `last_checked_at` per entity | **overwritten** each run |
| `entity_changes` (the change log) | append-only material deltas | **appended**, never overwritten |

**The timeline = the change log read in order.** To reconstruct a past point: take Current state and
replay deltas backward (north-star tooling; MVP just *stores* the deltas).

### Data model sketch (new tables)

```
tracked_entities
  id · workspace_id · tracker_id (FK) · entity_key (unique per tracker) · first_seen_at
  # MVP: exactly one row per Tracker (single-entity). Table stays multi-entity-ready.

entity_current_state
  entity_id (FK, unique) · tracker_id · fields JSONB (latest, conforms to locked field_schema)
  · content_hash · last_checked_at · updated_at
  # overwritten each material run; content_hash powers the hot-loop cheap pre-check (05b step 2)

entity_changes                         # the append-only change log
  id · entity_id (FK) · tracker_id · captured_at
  · delta JSONB            # { field: { from, to } }
  · materiality            # material | notable(=notable_signals-sourced)
  · decided_by             # code | agent   (audit of the materiality split)
  · source_ref             # url / blob key the change was observed from
  · note TEXT NULL         # optional agent rationale (the "why material")
```

- **No change → no row** in `entity_changes`; an unchanged refresh only bumps `last_checked_at`.
- `decided_by` records whether code or the agent ruled the change material (provenance seed).

### What it is NOT

- **Not the KB** — no `Document` rows, no embeddings, no indexing. ("Don't index crawled data" holds.)
- **Not `automation_runs`** — that's an orchestration artifact; this is the durable fact store.
- **Not a resurrected `pipeline_runs`.**

### Where it lives

- New CI-owned tables (in `app/db.py` alongside core entities, or a small `app/timeline/` package — decide
  at write-up). **Apache-2** (it stores facts; the moat is in Acquisition + the Maps extractor).
- Published to Zero full-row later if/when a UI needs live sync (deferred with the frontend).

## Work items

1. **Models + migration**: `tracked_entities` / `entity_current_state` / `entity_changes` + Alembic migration.
2. **Write API**: `upsert_current_state(...)` (overwrite) and `append_change(...)` (insert) used by the `05b` loop.
3. **Read API**: `query_timeline(tracker_id, …)` + `get_current_state(entity_id)` for the conversation/read side.
4. **Content-hash field**: store + expose `content_hash` so `05b` step 2 can short-circuit.
5. **Zero publication entry** (full-row) — wired but inert until a UI consumes it (deferred).

## Tests

- **No change → no row**: an unchanged refresh bumps `last_checked_at` only; `entity_changes` count is unchanged.
- **Append-only log**: a material refresh inserts exactly one `entity_changes` row and overwrites `entity_current_state`.
- **Provenance**: `decided_by` is `code` for threshold rules and `agent` for ambiguous calls.
- **Identity**: `entity_key` is unique per tracker; re-refresh of the same entity reuses the row.
- **Read API**: `query_timeline` returns deltas in `captured_at` order.

## Risks / trade-offs

- **First-run baseline**: with no prior `entity_current_state`, the diff has nothing to compare against —
  baseline semantics (silent establish vs flood the log) are an implementation-time call.
- **High-velocity entities**: append-only growth is bounded by change rate, but retention/archival for very
  chatty entities is deferred.
- **Schema-validate-on-write**: validating `fields` against the locked `field_schema` is a cheap integrity
  guard (lean: yes) but adds a write-path dependency on `05b`'s lock.

## Resolved decisions

1. Three stores: `tracked_entities` / `entity_current_state` / `entity_changes`.
2. Store deltas, not snapshots; **no change → no row**; storage ∝ rate of change.
3. CI-owned new tables; **not** KB, **not** `automation_runs`.
4. `content_hash` on current state powers the hot-loop cheap pre-check.
5. `decided_by` on changes records the code-vs-agent materiality provenance.
6. Single entity per Tracker for MVP; schema stays multi-entity-ready (additive later).

## Out of scope (hand-offs)

- **The writer** (hot loop, materiality, schema lock) → `05b`.
- **Backward-replay reconstruction**, trend/series read APIs, coverage-confidence, multi-entity scale, the
  resale/data-product surface → north star (deferred).
- **Live UI sync** (Zero consumption, dashboards) → frontend umbrella.

## Open questions (carry forward)

- ORM home: `app/db.py` vs a dedicated `app/timeline/` package.
- Whether `entity_current_state.fields` is validated against the locked `field_schema` at write time (lean: yes).
- Retention / archival policy for very high-velocity entities (deferred).
