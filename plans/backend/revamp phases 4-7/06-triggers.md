# Phase 6 — Triggers (the pluggable refresh clock)

> **Phase 6** of the CI-pivot revamp — the thinnest phase. **Build after** Phase 5 (`05b` exposes
> `refresh(tracker)`).
> **Depends on** `05b` (`refresh(tracker)`), `04b` (the REST manual/cron routes), and the SHIPPED
> automations subsystem (its schedule selector + `AutomationRun` + delivery).
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. This phase is **decoupled** — Intelligence (`05b`) has no
> dependency on it, and **automations is at most one optional adapter, never required**.

## Objective

Decide **when** a Tracker refreshes. Intelligence exposes a single entry point — **`refresh(tracker)`** —
and every trigger is just a caller. Intelligence never knows which trigger fired; remove any trigger and
the engine still works. This replaces the old Phase-6 cron scheduler — and the resolution is **not** to
rebuild a scheduler at all, but to **reuse the automations subsystem** for the in-app recurring path.

## Current state (cited)

- **`refresh(tracker)`** — the headless unit of work exposed by `05b`.
- **Automations schedule selector** — the already-hardened cron selector (`FOR UPDATE SKIP LOCKED`
  claiming, `next_fire_at` advance, self-heal, duplicate-run suppression, `catchup=False`), reusing the
  `croniter` util.
- **`AutomationRun`** — the existing run record + PENDING-gate (audit + idempotency).
- **Automations output/delivery** — the existing path that carries results to the user.
- **Access routes** (`04b`) — where the external-cron and manual REST endpoints live.

## Target design

### The adapters

| Adapter | Fired by | MVP? |
|---------|----------|------|
| **Manual** | user "refresh now" (chat tool / REST) | ✅ |
| **Agent** | the in-app agent calls `refresh` as a tool | ✅ |
| **External cron** | the user's own scheduler hits `POST /v1/trackers/{id}/refresh` | ✅ (zero infra on us) |
| **CI automation action** | a **CI action on the existing automations** — its schedule trigger fires `refresh(tracker)` **and delivers** the material changes | ✅ (the in-app recurrence + alert path) |

### Recurrence + delivery — a CI action on existing automations (NOT a new scheduler, NOT a new shape)

The SMB competitor-watch buyer needs **in-app recurrence** *and* **"tell me when it changes."** Instead of
building a bespoke tick, we **add a CI *action* to the existing automations subsystem**:

- **Schedule** → the automation's existing **schedule trigger** (the already-hardened selector). No new
  scheduler. **(closes old Gap B — scheduler rigor.)**
- **Run record + idempotency** → the automation's existing **`AutomationRun`** + PENDING-gate. No new run
  table. **(closes old Gap A — run/idempotency, see `05b`.)**
- **Delivery / alert** → the automation's existing **output/delivery** carries the material changes to the
  user. **(closes old Gap E — alert delivery.)**

**Why a CI *action*, not a new automation shape:** a new shape would duplicate triggers, runs, and delivery
that already exist. A single `refresh_tracker` action reuses all of it. (If implementation finds the action
too constraining, a thin CI-specific shape is the fallback — but the action is the default.)

### Decoupling is preserved (automations is still optional)

CI **core** — `refresh(tracker)` + Timeline (`05a`/`05b`) — has **zero** automations dependency and runs
via manual / agent / external-cron. Automations is the **optional adapter** that adds recurrence + delivery
+ audit for in-app users. So we honor "don't glue CI to automations" *and* get its machinery for free.

### Where it lives

- The **CI action** lives with automations (its action registry); it imports `refresh(tracker)` from
  `app/intelligence/`. No new scheduler/Beat task.
- The **external-cron** and **REST manual** paths are just Access-door routes (`POST
  /v1/trackers/{id}/refresh`) — `04b` plumbing.

## Work items

1. **Manual / agent triggers**: a `refresh_tracker(tracker_id)` chat tool + REST route → `refresh(tracker)`.
2. **External-cron route**: `POST /v1/trackers/{id}/refresh` (API-key authed) → `refresh(tracker)`.
3. **CI automation action**: register a `refresh_tracker` action in the automations action registry that
   calls `refresh(tracker)` and routes the resulting material changes into automations delivery.
4. **Concurrency guard**: a per-Tracker in-flight lock (belt-and-suspenders over the automation run-gate).

## Tests

- **Decoupling**: `refresh(tracker)` works via manual/agent/external-cron with automations disabled entirely.
- **Recurring path**: a scheduled CI action fires `refresh` on cron and delivers material changes; an
  unchanged refresh delivers nothing.
- **Idempotency**: a redelivered scheduled run (same `AutomationRun`) does not double-refresh.
- **External cron**: `POST /v1/trackers/{id}/refresh` triggers exactly one refresh; rejects bad auth.
- **Concurrency**: a second refresh while one is in flight is skipped/queued, not run concurrently.

## Risks / trade-offs

- **Action vs shape**: the CI action is the default; a thin CI automation shape is the fallback if the
  action proves too constraining.
- **Delivered payload shape** (agent-summarized vs raw deltas since last fire) — implementation-time call.
- **Double-guarding concurrency**: the per-Tracker lock overlaps the automation run-gate, but the lock also
  protects the manual/cron paths that don't go through automations.

## Resolved decisions

1. Intelligence exposes `refresh(tracker)`; all triggers are callers. Fully decoupled.
2. Adapters: manual · agent · external-cron · **CI automation action** (recurrence + delivery).
3. **No bespoke scheduler and no new run table** — the recurring path reuses the automations schedule
   selector + `AutomationRun`; delivery reuses automations' output. (Closes old Gaps A/B/E.)
4. Recurrence is a **CI *action*** on the existing automations, **not a new automation shape**.
5. CI core stays runnable with **zero** automations dependency (manual/agent/external-cron).

## Out of scope (hand-offs)

- **`refresh(tracker)` internals** (the hot loop, materiality) → `05b`.
- **The Timeline reads** the delivery summarizes → `05a`.
- **The chat tool surface** for manual/agent refresh → `07` (the `intelligence_agent` toolset).

## Open questions (carry forward)

- CI **action** vs a thin CI-specific automation **shape** (default: action; shape is the fallback).
- What the delivered payload looks like (summarized material changes vs raw deltas since last fire).
- Concurrency: per-Tracker lock granularity (like the connector indexing lock).
