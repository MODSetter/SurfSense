# Domain ⑤ — Triggers (the pluggable refresh clock) (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp. The thinnest domain.
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. This domain is **decoupled** — Intelligence (`03`)
> has no dependency on it, and **automations is at most one optional adapter, never required**.

## Purpose

Decide **when** a Tracker refreshes. Intelligence exposes a single entry point — **`refresh(tracker)`** —
and every trigger is just a caller. Intelligence never knows which trigger fired; remove any trigger
and the engine still works.

This replaces Phase 6's cron scheduler — and the resolution is **not** to rebuild a scheduler at all,
but to **reuse the automations subsystem** for the in-app recurring path (it already has a hardened
clock + run record + delivery). A trigger only ever calls `refresh(tracker)`.

## The adapters

| Adapter | Fired by | MVP? |
|---------|----------|------|
| **Manual** | user "refresh now" (chat tool / REST) | ✅ |
| **Agent** | the in-app agent calls `refresh` as a tool | ✅ |
| **External cron** | the user's own scheduler hits `POST /v1/trackers/{id}/refresh` | ✅ (zero infra on us) |
| **CI automation action** | a **CI action on the existing automations** — its schedule trigger fires `refresh(tracker)` **and delivers** the material changes | ✅ (the in-app recurrence + alert path) |

## Recurrence + delivery — a CI action on existing automations (NOT a new scheduler, NOT a new shape)

The SMB competitor-watch buyer needs **in-app recurrence** *and* **"tell me when it changes"**. Instead
of building a bespoke tick (which — done correctly — still needs `FOR UPDATE SKIP LOCKED` claiming,
`next_fire_at` advance, self-heal, duplicate-run suppression, `catchup=False`), we **add a CI *action*
to the existing automations subsystem**:

- **Schedule** → the automation's existing **schedule trigger** (the already-hardened selector). No new
  scheduler. **(closes the old Gap B — scheduler rigor.)**
- **Run record + idempotency** → the automation's existing **`AutomationRun`** + PENDING-gate. No new
  run table. **(closes the old Gap A — run/idempotency, see `03`.)**
- **Delivery / alert** → the automation's existing **output/delivery** carries the material changes to
  the user. **(closes the old Gap E — alert delivery.)**

**Why a CI *action*, not a new automation shape:** a new shape would duplicate triggers, runs, and
delivery that already exist. A single `refresh_tracker` action reuses all of it. (If implementation finds
the action too constraining, a thin CI-specific shape is the fallback — but the action is the default.)

### Decoupling is preserved (automations is still optional)

CI **core** — `refresh(tracker)` + Timeline (`03`/`04`) — has **zero** automations dependency and runs via
manual / agent / external-cron. Automations is the **optional adapter** that adds recurrence + delivery
+ audit for in-app users. So we honor "don't glue CI to automations" *and* get its machinery for free.

## Where it lives / decoupling

- The **CI action** lives with automations (its action registry); it imports `refresh(tracker)` from
  `app/intelligence/`. No new scheduler/Beat task.
- The **external-cron** and **REST manual** paths are just Access-door routes (`POST
  /v1/trackers/{id}/refresh`) — Domain ② plumbing.

## Locked decisions

1. Intelligence exposes `refresh(tracker)`; all triggers are callers. Fully decoupled.
2. Adapters: manual · agent · external-cron · **CI automation action** (recurrence + delivery).
3. **No bespoke scheduler and no new run table** — the recurring path reuses the automations schedule
   selector + `AutomationRun`; delivery reuses automations' output. (Closes old Gaps A/B/E.)
4. Recurrence is a **CI *action*** on the existing automations, **not a new automation shape**.
5. CI core stays runnable with **zero** automations dependency (manual/agent/external-cron).

## Open questions (carry forward)

- CI **action** vs a thin CI-specific automation **shape** (default: action; shape is the fallback).
- What the delivered payload looks like (the material `entity_changes` since last fire — summarized by
  the agent, or raw deltas).
- Concurrency: skip a refresh if the Tracker already has one in flight (per-Tracker lock, like the connector
  indexing lock) — even with the automation run-gate, belt-and-suspenders.
