# Domain ④ — Timeline (the moat asset) (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp. Pairs with `03-intelligence.md` (the process
> that writes it).
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. The Timeline is **CI-owned, new tables** — it is
> **not** the Knowledge Base (documents/embeddings) and **not** `automation_runs`.

## Purpose

Durably store the **time-shaped truth** for each Tracker. This is the asset: **time is the moat** —
accumulated history a later entrant cannot re-create. Design rule: **store deltas, not snapshots —
no change, no row.** Storage grows with the *rate of change*, not the number of runs.

## The state / process split

Intelligence (`03`) is the only **writer** (via the hot loop). **Readers** — the Conversation domain
today, future dashboards / alerts / the deferred resale product — read the Timeline **directly,
without running the loop**. That separation is the reason Timeline is its own domain.

## The three stores

| Store | Role | Write pattern |
|-------|------|---------------|
| `tracked_entities` | stable identity per tracked thing (the Tracker's `identity_rule` → `entity_key`) | written **once** |
| `entity_current_state` | latest values + `content_hash` + `last_checked_at` per entity | **overwritten** each run |
| `entity_changes` (the change log) | append-only material deltas | **appended**, never overwritten |

**The timeline = the change log read in order.** To reconstruct a past point: take Current state and
replay deltas backward (north-star tooling; not built in MVP — we just *store* the deltas).

## Data model sketch (new tables)

```
tracked_entities
  id · workspace_id · tracker_id (FK) · entity_key (unique per tracker) · first_seen_at
  # MVP: exactly one row per Tracker (single-entity). Table stays multi-entity-ready.

entity_current_state
  entity_id (FK, unique) · tracker_id · fields JSONB (latest, conforms to locked field_schema)
  · content_hash · last_checked_at · updated_at
  # overwritten each material run; content_hash powers the hot-loop cheap pre-check (03 step 2)

entity_changes                         # the append-only change log
  id · entity_id (FK) · tracker_id · captured_at
  · delta JSONB            # { field: { from, to } }
  · materiality            # material | notable(=notable_signals-sourced)
  · decided_by             # code | agent   (audit of the materiality split)
  · source_ref             # url / blob key the change was observed from
  · note TEXT NULL         # optional agent rationale (the "why material")
```

- **No change → no row** in `entity_changes`; an unchanged refresh only bumps
  `entity_current_state.last_checked_at`.
- `decided_by` records whether code or the agent ruled the change material (provenance seed for the
  north-star explainability work).

## What it is NOT

- **Not the KB** — no `Document` rows, no embeddings, no indexing pipeline. (The meeting's "don't
  index crawled data" holds.)
- **Not `automation_runs`** — that's an orchestration artifact; this is the durable fact store.
- **Not a resurrected `pipeline_runs`.**

## Where it lives

- New CI-owned tables (in `app/db.py` alongside the other core entities, or a small `app/timeline/`
  package — decide at write-up). **Apache-2** (it stores facts; the moat is in Acquisition + the Maps
  extractor, not here).
- Published to Zero full-row later if/when a UI needs live sync (deferred with the frontend).

## MVP cut vs north star

- **MVP:** the three stores · single entity per Tracker · deltas with `decided_by`/`source_ref` ·
  `content_hash` pre-check support.
- **North star (deferred):** backward-replay reconstruction queries · trend/series read APIs ·
  coverage-confidence metadata · multi-entity scale · the resale/data-product surface.

## Locked decisions

1. Three stores: `tracked_entities` / `entity_current_state` / `entity_changes`.
2. Store deltas, not snapshots; **no change → no row**; storage ∝ rate of change.
3. CI-owned new tables; **not** KB, **not** `automation_runs`.
4. `content_hash` on current state powers the hot-loop cheap pre-check.
5. `decided_by` on changes records the code-vs-agent materiality provenance.
6. Single entity per Tracker for MVP; schema stays multi-entity-ready (additive later).

## Open questions (carry forward)

- ORM home: `app/db.py` vs a dedicated `app/timeline/` package.
- Whether `entity_current_state.fields` should be validated against the Tracker's locked `field_schema`
  at write time (lean: yes, cheap integrity guard).
- Retention / archival policy for very high-velocity entities (deferred).
