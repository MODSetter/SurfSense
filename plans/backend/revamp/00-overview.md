# Phase 4 → end revamp — Overview & reconciliation (CI pivot · WIP)

> **What this is.** The CI pivot re-architects the old "pipeline" phases (`04`–`07`) into small,
> single-responsibility domains. This file is the map + the reconciliation against the old plans.
> **Scope guardrail:** Phases **1–3 are SHIPPED/FIXED** (rename/DB, proxy/captcha/stealth, crawl
> billing). The revamp is **Phase 4 → end only**. We do **not** touch 1–3.

## The two products

```
PRODUCT A — stateless utility      ① Capabilities + ② Access
  call a verb → get data → bill.  Nothing persists.

PRODUCT B — decision-grounded CI   ③ Intelligence + ④ Timeline  (+ ⑤ Triggers to drive it)
  a Lens accumulates structured signal over time.  The Timeline is the moat.
```

## The domain map

```
            FIXED (Phases 1–3)                        OUR SCOPE (Phase 4 → end)
   ┌─────────────────────────────────┐   ┌──────────────────────────────────────────────┐
   │  Acquisition                     │   │  ① Capabilities   typed verbs over Acquisition │
   │   proprietary/web_crawler        │◄──┤  ② Access         chat · REST · MCP doors      │
   │   CrawlOutcome · billing (03c)   │   │  ③ Intelligence   Lens · schema · hot loop     │
   │                                  │   │  ④ Timeline       3-store delta state (moat)   │
   │                                  │   │  ⑤ Triggers       pluggable refresh clock      │
   │                                  │   │  ⑥ Orchestration  CI-expert subagent + tools   │
   └─────────────────────────────────┘   └──────────────────────────────────────────────┘
        data engine (untouched)             stateless ①② → stateful ③④ , driven by ⑤ , fronted by ⑥
```

| # | Domain | One line | Doc |
|---|--------|----------|-----|
| ① | Capabilities | Acquisition → typed callable verbs (`web.scrape`, `web.discover`, `maps.*`) | `01-capabilities.md` |
| ② | Access | expose verbs to callers, authed + metered (chat / REST / MCP) | `02-access.md` |
| ③ | Intelligence | the Lens, agent-designed locked schema, hot loop (agent judges, code computes) | `03-intelligence.md` |
| ④ | Timeline | durable time-shaped truth; deltas not snapshots; no change → no row | `04-timeline.md` |
| ⑤ | Triggers | when a Lens refreshes; `refresh(lens)` callers; recurrence+delivery = optional CI action on automations | `05-triggers.md` |
| ⑥ | Orchestration | the human-facing CI-expert subagent (intent routing, verb chains, Lens crafting) + its tools | `06-orchestration.md` |

## Reconciliation with the old plans

| Old plan | Fate | Where it goes |
|----------|------|---------------|
| `04a-connector-category.md` | **demoted to hygiene** | the genuine MCP-routing fix survives in ② (consume-user-MCP); the taxonomy work is not core |
| `04b-source-discovery.md` | **absorbed** | becomes the `web.discover` capability in ① |
| `05-pipelines-model.md` | **dissolved** | the "pipeline" concept → the `Lens` (③) + Timeline tables (④); no `pipeline`/`pipeline_runs` |
| `06-pipelines-exec.md` | **dissolved** | execution → the hot loop (③); scheduling/runs/delivery → **reuse automations** via a CI action (⑤) — its selector + `AutomationRun`, **not** a rebuilt cron |
| `07-upload-pipeline-kb.md` | **dropped (crawl→KB + uploads-as-pipeline audit)** | "don't index *crawled* data" holds. **User file-upload-to-KB remains a pre-existing, untouched feature** (uploads still become indexed KB Documents). For CI, uploads are routed to a dedicated **folder** and may feed the judge (`03`, F) |

**Net:** the old `05/06/07` pipeline+KB stack is replaced by `①②③④⑤⑥`. KB indexing of *crawled* data is
out; *user uploads* still work (and gain a CI context-folder role).

## Build sequence (proposed)

1. **① Capabilities** — registry + the verb `executor`s over Acquisition (unblocks everything).
2. **② Access** — REST + API keys (day-one endpoints) and chat tools; MCP fast-follow.
3. **④ Timeline** — the three tables (state must exist before the loop writes it).
4. **③ Intelligence** — schema-design agent + hot loop + materiality evaluator.
5. **⑤ Triggers** — manual/agent/external-cron; then the CI **automation action** (recurrence +
   delivery) reusing the automations selector + `AutomationRun`.
6. **⑥ Orchestration** — the `analyst` CI-expert subagent + tools + prompt (the human-facing seam;
   built atop ①–④, can grow alongside them).

## Consolidated open forks (need your call)

1. Primitive **name** — using `Lens` as a working label; confirm or replace.
2. Schema **review-&-lock** UX before frontend exists — pure-chat confirmation for MVP?
3. Timeline ORM home — `app/db.py` vs dedicated `app/timeline/`.
4. Recurrence = CI **action** on automations (default) vs a thin CI automation **shape** (fallback).

*(Resolved: the "built-in scheduler tick" fork — we reuse the automations schedule selector via a CI
action instead of building a tick. See `05`.)*

## Confirmed decisions (locked across docs)

- **Natural language is the only human-facing surface.** Users never name verbs; the chat agent
  understands intent, composes the verbs, and answers in plain language. An **intent router**
  classifies one-shot (A) vs standing-concern (B) from the wording (one clarifying question if
  ambiguous). Raw verbs live only on the REST/MCP dev doors.
- MVP surface = Google Maps actor + general web crawler, exposed chat + REST (MCP fast-follow).
- Verbs namespaced per platform (`web.*`, `maps.*`); `web.scrape` takes a URL **array** (inline-or-job).
- **Don't index** crawled data into the KB; the Timeline (deltas) is the only persisted CI state.
- CI is **decoupled from automations** (automations = one optional Trigger adapter).
- Intelligence: **agent-designed schema** (sample-grounded, human-locked, versioned) in MVP; single
  entity per Lens; materiality = code thresholds (numeric/clear) + agent on ambiguous; content-hash
  pre-check before LLM spend.
- Orchestration is a first-class deliverable: a **net-new CI-expert subagent** (`analyst`, working
  name) on the existing chat runtime, with registry-backed verb tools + Lens/Timeline tools; intent
  routing lives in its prompt, the headless logic stays in ③/④.
- **Recurrence + alert delivery = a CI *action* on the existing automations** (not a new scheduler,
  not a new shape): reuses the hardened schedule selector, `AutomationRun` (audit + idempotency), and
  automations' delivery. CI core still runs with **zero** automations dependency (manual/agent/cron).
- **No new run table:** refresh audit/idempotency ride `AutomationRun` or the chat job record; billing
  idempotency is per-capability-call + the content-hash pre-check. Only the Timeline is new state.
- **Billing is delegated to the billing service:** verbs declare a `billing_unit`; `03c` is the first
  provider; `maps.*` / `web.discover` register their own units there (pricing stays pluggable).
- The **Google Maps actor is net-new** (not in shipped Phases 1–3) and is designed/built as a
  **separate effort**; `maps.*` verbs are contracts against it and don't block this design.
- **CI context files (F):** files uploaded in a CI chat go into the **KB as normal** (indexed), routed
  to a dedicated `Folder`, and may feed the materiality judge via KB retrieval — the user's private
  context shapes what counts as material. ("Don't index" applies only to *crawled* data.)
- License: new domains **Apache-2**; the moat stays in proprietary Acquisition + the Maps extractor.
