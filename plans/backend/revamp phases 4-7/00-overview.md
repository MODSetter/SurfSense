# Phase 4 → end revamp — Overview & phase index (CI pivot · WIP)

> **What this is.** The CI pivot re-architects the old "pipeline" Phases `04`–`07` into small,
> single-responsibility domains, now packaged as **4 phases (04–07)** that mirror the slots they replace.
> This file is the map + the reconciliation + the subplan index. **End-to-end flow diagrams (stateless &
> stateful paths) live in `00b-pipeline-diagrams.md`.**
> **Scope guardrail:** Phases **1–3 are SHIPPED/FIXED** (rename/DB, proxy/captcha/stealth, crawl billing).
> The revamp is **Phase 4 → end only**. We do **not** touch 1–3.
>
> **Citation verification — 2026-06-30 (principal-engineer pass).** All load-bearing code citations in this
> revamp were re-checked against `surfsense_backend`. Confirmed accurate: the schedule selector
> (`selector.py` — `FOR UPDATE SKIP LOCKED`, `next_fire_at`, self-heal, `catchup=False`, `croniter`), the
> `AutomationRun` model/fields, `format_to_structured_document(exclude_metadata=True)` content-hashing, the
> MCP routing gap (`constants.py::CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS`), the connector enum, and the
> `MANUAL` trigger placeholder. **Corrected during this pass:** (a) automations have **no** delivery/
> notification path and `automation_runs.output` is never written — CI alerts wire to `app/notifications/`
> (`06`/`05b`); (b) the automation PENDING-gate is **not atomic** — the per-Tracker lock is the real
> concurrency guard (`06`/`05b`); (c) folder upload uses `root_folder_id` (not `destination_folder`) and KB
> folder scoping goes through `referenced_document_ids → SearchScope.document_ids` (`05b`); (d) the billable
> predicate is `SUCCESS and outcome.result`, to be single-sourced in the executor (`04a`).

## The two products

```
PRODUCT A — stateless utility      Phase 04 (Capabilities + Access)
  call a verb → get data → bill.  Nothing persists.

PRODUCT B — decision-grounded CI   Phase 05 (Intelligence + Timeline)  (+ 06 Triggers, 07 Orchestration)
  a Tracker accumulates structured signal over time.  The Timeline is the moat.
```

## The phases (this revamp)

| Phase | Subplan(s) | Domain(s) | One line | Ships |
|-------|-----------|-----------|----------|-------|
| **04 — Capabilities & Access** | `04a-capabilities.md` · `04b-access.md` | ① + ② | typed verbs over Acquisition + the chat/REST/MCP doors | **Product A** (revenue day one) |
| **05 — Intelligence & Timeline** | `05a-timeline.md` · `05b-intelligence.md` | ④ + ③ | the Tracker, locked schema, hot loop + the 3-store delta moat | **Product B engine** |
| **06 — Triggers** | `06-triggers.md` | ⑤ | the pluggable refresh clock; recurrence+delivery = optional CI action on automations | recurrence + alerts |
| **07 — Orchestration** | `07-orchestration.md` | ⑥ | the `intelligence_agent` CI-expert subagent (intent routing, verb chains, Tracker crafting) | the human-facing CI experience |

> **Build order = phase order.** `04a → 04b` (unblocks everything; ships Product A) → `05a → 05b`
> (state before the loop that writes it) → `06` (drive it) → `07` (front it). `04a` first because every
> other phase calls into the capability registry.

## Domain ↔ phase map

```
            FIXED (Phases 1–3)                        OUR SCOPE (Phase 04 → 07)
   ┌─────────────────────────────────┐   ┌──────────────────────────────────────────────┐
   │  Acquisition                     │   │  04a Capabilities  typed verbs over Acquisition │
   │   proprietary/web_crawler        │◄──┤  04b Access        chat · REST · MCP doors      │
   │   CrawlOutcome · billing (03c)   │   │  05a Timeline      3-store delta state (moat)   │
   │                                  │   │  05b Intelligence  Tracker · schema · hot loop  │
   │                                  │   │  06  Triggers      pluggable refresh clock      │
   │                                  │   │  07  Orchestration CI-expert subagent + tools   │
   └─────────────────────────────────┘   └──────────────────────────────────────────────┘
        data engine (untouched)             stateless 04 → stateful 05 , driven by 06 , fronted by 07
```

## Reconciliation with the old plans

| Old plan | Fate | Where it goes |
|----------|------|---------------|
| `04a-connector-category.md` | **demoted to hygiene** | the genuine MCP-routing fix survives in `04b` (consume-user-MCP); the taxonomy work is not core |
| `04b-source-discovery.md` | **absorbed** | becomes the `web.discover` capability in `04a` |
| `05-pipelines-model.md` | **dissolved** | the "pipeline" concept → the `Tracker` (`05b`) + Timeline tables (`05a`); no `pipeline`/`pipeline_runs` |
| `06-pipelines-exec.md` | **dissolved** | execution → the hot loop (`05b`); scheduling/runs/delivery → **reuse automations** via a CI action (`06`) — its selector + `AutomationRun`, **not** a rebuilt cron |
| `07-upload-pipeline-kb.md` | **dropped (crawl→KB + uploads-as-pipeline audit)** | "don't index *crawled* data" holds. **User file-upload-to-KB remains a pre-existing, untouched feature.** For CI, uploads are routed to a dedicated **folder** and may feed the judge (`05b`) |

**Net:** the old `05/06/07` pipeline+KB stack is replaced by the new `04`–`07`. KB indexing of *crawled*
data is out; *user uploads* still work (and gain a CI context-folder role).

## Confirmed decisions (locked across phases)

- **Natural language is the only human-facing surface.** Users never name verbs; the chat agent
  understands intent, composes verbs, answers in plain language. An **intent router** classifies one-shot
  (A) vs standing-concern (B) from the wording (one clarifying question if ambiguous). Raw verbs live only
  on the REST/MCP dev doors.
- MVP surface = the **general web crawler + search** (`web.scrape` + `web.discover`), exposed chat + REST (MCP fast-follow). **Platform-specific scrapers are a family of individual endpoints added incrementally — none (incl. Google Maps) is committed for MVP;** each is just another verb → agent tool + dev API-key REST endpoint.
- Verbs namespaced per platform (`web.*`, and `<platform>.*` per scraper, e.g. `maps.*` as an example); `web.scrape` takes a URL **array** (inline-or-job).
- **Don't index** crawled data into the KB; the Timeline (deltas) is the only persisted CI state.
- CI is **decoupled from automations** (automations = one optional Trigger adapter).
- Intelligence: **agent-designed schema** (sample-grounded, human-locked, versioned) in MVP; single entity
  per Tracker; materiality = code thresholds (numeric/clear) + agent on ambiguous; content-hash pre-check.
- Orchestration is a first-class deliverable: a **net-new CI-expert subagent** (`intelligence_agent`) on
  the existing chat runtime, with registry-backed verb tools + Tracker/Timeline tools.
- **Recurrence + alert delivery = a CI *action* on the existing automations** (not a new scheduler, not a
  new shape): reuses the hardened schedule selector, `AutomationRun` (audit + idempotency), and delivery.
  CI core still runs with **zero** automations dependency (manual/agent/cron).
- **No new run table:** refresh audit/idempotency ride `AutomationRun` or the chat job record; billing
  idempotency is per-capability-call + the content-hash pre-check. Only the Timeline is new state.
- **Billing is delegated to the billing service:** verbs declare a `billing_unit`; `03c` is the first
  provider; `maps.*` / `web.discover` register their own units there.
- The **Google Maps actor is net-new** (not in shipped Phases 1–3) and is designed/built as a **separate
  effort**; `maps.*` verbs are contracts against it and don't block this design.
- **CI context files:** files uploaded in a CI chat go into the **KB as normal** (indexed), routed to a
  dedicated `Folder`, and may feed the materiality judge via KB retrieval. ("Don't index" applies only to
  *crawled* data.)
- **Names:** primitive = `Tracker`, subagent = `intelligence_agent` (Intelligence Agent).
- License: new domains **Apache-2**; the moat stays in proprietary Acquisition + the Maps extractor.

## Cross-phase open forks (need your call)

1. Schema **review-&-lock** UX before frontend exists — pure-chat confirmation for MVP? (`05b`)
2. Timeline ORM home — `app/db.py` vs dedicated `app/timeline/`. (`05a`)
3. Recurrence = CI **action** on automations (default) vs a thin CI automation **shape** (fallback). (`06`)

*(Resolved: the "built-in scheduler tick" fork — reuse the automations schedule selector via a CI action
instead of building a tick. See `06`.)*

> **Per-phase implementation-time questions** (refresh failure path, first-run baseline, tracker lifecycle,
> mid-run balance, concurrency lock, delivery payload shape) are intentionally **not** resolved here — they
> don't change any boundary, contract, or data shape, and are settled when each phase is built.

## Subplan index (revamp)

| Phase | Subplan file | Status |
|-------|--------------|--------|
| — | `00b-pipeline-diagrams.md` | end-to-end flow diagrams |
| 04 | `04a-capabilities.md` | drafted |
| 04 | `04b-access.md` | drafted |
| 05 | `05a-timeline.md` | drafted |
| 05 | `05b-intelligence.md` | drafted |
| 06 | `06-triggers.md` | drafted |
| 07 | `07-orchestration.md` | drafted |
