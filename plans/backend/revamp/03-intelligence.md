# Domain ③ — Intelligence (the decision-grounded engine) (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp. Pairs with `04-timeline.md` (the state it writes).
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. This is net-new and is **not** the KB and **not**
> the automations subsystem.
> **Working name:** the standing-concern primitive is called a **Lens** (provisional — easily renamed).

## The stateless / stateful line

```
STATELESS  (Product A):  ① Capabilities + ② Access      → call → data → bill, nothing persists
STATEFUL   (Product B):  ③ Intelligence + ④ Timeline    → the Timeline IS the state
```

Intelligence is the **process** that mutates state; Timeline (`04`) is the **state**. Everything
below the Access→Intelligence boundary stays pure functions.

## Purpose

Turn repeated capability calls into **decision-relevant structured signal**. The motto: **the agent
judges, code computes.** This replaces the old "pipeline" as the *standing concern*.

## The primitive — `Lens`

A saved, decision-grounded subject that accumulates structured signal over time:

| Field | Meaning |
|-------|---------|
| `decision` | the question being tracked toward ("is this competitor pulling ahead?") |
| `capability_binding` | which verb + input feeds it (`maps.place(X)`, `web.scrape([Y])`) |
| `definition` (locked, versioned) | `{ field_schema, identity_rule, materiality }` — the agent-drafted, human-locked contract |
| `status` | `draft` → `locked`/`active` |

One **entity per Lens for MVP** (one place / one URL). Multi-entity (`maps.search → many`) is deferred
(the Timeline model stays multi-entity-ready so it's additive).

## Setup (once) — the agent-designed schema flow (IN MVP)

The product must not be rigid: **we cannot author one schema that serves everyone**, so the schema is
derived from the *user's* decision by an agent and locked by the human. Conversationally (chat-first,
no UI needed):

1. **Bind** a capability + input (the thing to track).
2. **Sample fetch** — one real capability call so the agent drafts against *actual* returned data,
   not a hallucinated shape.
3. **Agent drafts the `definition`** from `decision` + the sample:
   - `field_schema` — the fields that matter + types (structured-output contract).
   - `materiality` — per-field rules (numeric thresholds where possible; "ask agent" otherwise).
   - `identity_rule` — the stable entity key (e.g. Maps `place_id`, canonical URL).
   - a reserved **`notable_signals`** escape-hatch field for the unanticipated.
4. **Human reviews & locks** (in chat: "looks good" / "add field X"). Locked ⇒ stable run-to-run.
5. **Versioned** — a locked `definition` is a snapshot; edits create a new version (mirrors how
   `automations` snapshots `definition`).

## The hot loop (per refresh) — `refresh(lens)`

1. **Crawl** — call the bound capability (Domain ①) → raw data.
2. **Cheap pre-check** — content hash via the existing
   `WebCrawlerConnector.format_to_structured_document(exclude_metadata=True)`; identical hash to the
   stored `content_hash` → stamp `last_checked_at`, **stop** (no LLM cost).
3. **Fill** — agent conforms raw data to the **locked `field_schema`** via structured output; it does
   **not** invent fields. Unanticipated observations go into `notable_signals`.
4. **Diff (code)** — deterministic compare of the new record vs Current state (`04`) → raw deltas.
5. **Judge — the materiality split:**
   - **deterministic (code):** numeric / clear-cut rules from `materiality`, applied for free, 100%
     reproducible. e.g. `rating Δ≥0.2 → material`, `review_count Δ≥10 → material`, `1¢ price wobble
     → noise`, `any hours change → material`.
   - **agent (only on ambiguous):** anything a rule can't decide — reworded `description`, a new
     `notable_signals` entry, "does this matter *for the decision*?" → one LLM call rules
     material/noise.
6. **Append** — if material: write a Change + update Current state (`04`). Else: only `last_checked_at`.
   **No change → no row.**

**Worked example (`maps.place` refresh):**
```
rating 4.4 → 4.3 (Δ0.1)   → code: < 0.2 → NOISE      (no LLM)
review_count 312 → 470    → code: ≥ 10 → MATERIAL    (no LLM)
hours unchanged           → no delta
description reworded       → code: no rule → ASK AGENT → NOISE
⇒ one Change row (review spike); one cheap LLM call; zero LLM on the rating tick.
```

## Where it lives / decoupling

- New **Apache-2** package `app/intelligence/` (the schema-design agent, the hot loop, the materiality
  evaluator). Calls capability `executor`s directly (not through a door).
- Exposes **`refresh(lens)`**. *Who* calls it (manual / agent / external cron / optional automation) is
  the **Triggers** domain's concern — Intelligence has **no dependency** on any scheduler.

## Refresh execution & idempotency — ride the invoking surface (no new run table)

`refresh(lens)` is a **headless unit of work**; the **run/audit record + idempotency live on whatever
surface invoked it**, so we do *not* rebuild old Phase-6 `pipeline_runs`:

- **Recurring (in-app):** invoked by the **CI automation action** (`05`) → the existing
  **`AutomationRun`** is the run record (status / error / timing / `step_results`) and the automations
  executor already provides the **PENDING→running idempotency gate** (safe under Celery `acks_late`
  redelivery). This is exactly the rigor old `06` hand-built — reused, not re-written.
- **Chat (manual / agent):** invoked via the chat **job record** (`01`) + `deliverable_wait` — status
  lives there.
- **Billing idempotency is per *capability call*, not per run:** each `executor` bills a success once
  via the billing service (`01`); the **content-hash pre-check** (step 2) is what prevents needless
  re-crawls/charges on an unchanged page. So no run-level `charged_micros` ledger is required for MVP.

Net: the only genuinely new state is the **Timeline** (`04`); execution accounting is borrowed from
`AutomationRun` / the job record.

## User-supplied context files (the F idea, generalized)

When a user uploads a file *in a CI chat* (e.g. "our own price list", a competitor brochure), it goes
into the **KB as normal** — uploads create `Document`s and are indexed/embedded, exactly as today.
**(The "don't index" rule applies only to *crawled* data, not to user uploads.)** The CI-specific part
is purely **organization + use**:

- **Routed to a dedicated folder** for that CI chat/Lens (reuse the existing folder-upload /
  `destination_folder` machinery), so the chat's reference files are scoped together.
- **The judge step (5) may consult them** — retrieved from the KB, scoped to that folder — when ruling
  materiality:

```
competitor price 12.00 → 9.90   + user's context file says "our price is 10.00"
   → agent: competitor crossed *below our price* → MATERIAL (and explain why)
```

So the user's private context **shapes what counts as material** — a real differentiator — and it
reuses the existing KB upload + folder + retrieval machinery (nothing new). **MVP-optional** (the loop
works without it); design the seam now so the judge can read the folder later.

## MVP cut vs north star

- **MVP:** agent-designed-schema flow (conversational, sample-grounded, human-locked) · single entity
  per Lens · the hot loop with content-hash pre-check + code-threshold + agent-on-ambiguous ·
  `refresh(lens)` fired manually / by agent / by external cron.
- **North star (deferred):** schema **auto-evolution** from recurring `notable_signals` · multi-entity
  Lenses (`maps.search`) · backward-replay reconstruction · coverage-confidence · full
  provenance/explainability · the resale/data-product stage.

## Locked decisions

1. `Lens` (provisional name) is the standing-concern primitive; replaces "pipeline".
2. Stateless (①②/Product A) vs stateful (③④/Product B) is the Access→Intelligence boundary.
3. **Agent-designed schema flow is in MVP** (not hand-authored) — sample-grounded, human-locked, versioned.
4. Single entity per Lens for MVP.
5. Materiality = deterministic numeric/clear rules in code + agent only on ambiguous.
6. Content-hash pre-check short-circuits unchanged pages before any LLM spend.
7. `app/intelligence/` Apache-2; `refresh(lens)` is trigger-agnostic.
8. **No new run table** — refresh audit/idempotency ride `AutomationRun` (recurring) or the chat job
   record; billing idempotency is per-capability-call + the content-hash gate. Only Timeline (`04`) is
   new state.
9. **CI context folder** (F): user files uploaded in a CI chat go into the **KB as normal** (indexed),
   routed to a dedicated `Folder`, and may feed the judge step via KB retrieval. The "don't index"
   rule is for *crawled* data only. MVP-optional seam.

## Open questions (carry forward)

- How the schema-design agent surfaces the "review & lock" step before the frontend exists (pure-chat
  confirmation for MVP?).
- Versioning policy on re-lock (new version vs in-place) — lean new version.
- Where the schema-design agent itself runs (a setup capability? a chat sub-flow?).
- Context-folder → judge wiring (how much of the folder to load; per-Lens vs per-chat scope).
