# Phase 5b — Intelligence (the decision-grounded engine)

> Part of **Phase 5 — Intelligence & Timeline**. Sibling: `05a-timeline.md` (the state it writes).
> **Build after** `05a` (the tables) and `04a` (the verbs it calls). Together, `05a + 05b` ship the
> **Product B engine** (the Tracker, locked schema, hot loop, deltas).
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. This is net-new and is **not** the KB and **not** the
> automations subsystem.
> **Name:** the standing-concern primitive is the **Tracker**.

## Objective

Turn repeated capability calls into **decision-relevant structured signal**. The motto: **the agent
judges, code computes.** This replaces the old "pipeline" as the *standing concern*: Intelligence is the
**process** that mutates state; Timeline (`05a`) is the **state**. Everything below the
Access→Intelligence boundary stays pure functions.

```
STATELESS (Product A):  04a Capabilities + 04b Access   → call → data → bill, nothing persists
STATEFUL  (Product B):  05b Intelligence + 05a Timeline  → the Timeline IS the state
```

## Current state (cited)

- **Capability executors** (`04a`) — called directly by the loop (not through a door).
- **Content-hash pre-check** — `WebCrawlerConnector.format_to_structured_document(exclude_metadata=True)`
  produces the stable text the loop hashes against `entity_current_state.content_hash` (`05a`).
- **Run/audit substrate to reuse** — the existing **`AutomationRun`** (status/error/timing/`step_results`)
  + the automations executor's PENDING→running idempotency gate (safe under Celery `acks_late`); and the
  chat **job record** (`04a`) + `deliverable_wait`. **No new run table.**
- **CI context uploads** — the existing folder-upload / `destination_folder` machinery + KB retrieval.

## Target design

### The primitive — `Tracker`

A saved, decision-grounded subject that accumulates structured signal over time:

| Field | Meaning |
|-------|---------|
| `decision` | the question being tracked toward ("is this competitor pulling ahead?") |
| `capability_binding` | which verb + input feeds it (`maps.place(X)`, `web.scrape([Y])`) |
| `definition` (locked, versioned) | `{ field_schema, identity_rule, materiality }` — the agent-drafted, human-locked contract |
| `status` | `draft` → `locked`/`active` |

One **entity per Tracker for MVP** (one place / one URL). Multi-entity (`maps.search → many`) is deferred
(the `05a` model stays multi-entity-ready so it's additive).

### Setup (once) — the agent-designed schema flow (IN MVP)

The product must not be rigid: **we cannot author one schema that serves everyone**, so the schema is
derived from the *user's* decision by an agent and locked by the human. Conversationally (chat-first):

1. **Bind** a capability + input.
2. **Sample fetch** — one real capability call so the agent drafts against *actual* returned data.
3. **Agent drafts the `definition`** from `decision` + the sample: `field_schema` (fields + types),
   `materiality` (numeric thresholds where possible; "ask agent" otherwise), `identity_rule` (stable
   entity key — Maps `place_id`, canonical URL), and a reserved **`notable_signals`** escape-hatch field.
4. **Human reviews & locks** (in chat: "looks good" / "add field X"). Locked ⇒ stable run-to-run.
5. **Versioned** — a locked `definition` is a snapshot; edits create a new version (mirrors how
   `automations` snapshots `definition`).

### The hot loop (per refresh) — `refresh(tracker)`

1. **Crawl** — call the bound capability (`04a`) → raw data.
2. **Cheap pre-check** — content hash; identical to the stored `content_hash` → stamp `last_checked_at`,
   **stop** (no LLM cost).
3. **Fill** — agent conforms raw data to the **locked `field_schema`** via structured output; it does
   **not** invent fields. Unanticipated observations go into `notable_signals`.
4. **Diff (code)** — deterministic compare of the new record vs Current state (`05a`) → raw deltas.
5. **Judge — the materiality split:**
   - **deterministic (code):** numeric/clear-cut rules from `materiality`, applied for free, 100%
     reproducible (e.g. `rating Δ≥0.2 → material`, `review_count Δ≥10 → material`, `1¢ wobble → noise`).
   - **agent (only on ambiguous):** anything a rule can't decide — reworded `description`, a new
     `notable_signals` entry → one LLM call rules material/noise.
6. **Append** — if material: write a Change + update Current state (`05a`). Else: only `last_checked_at`.
   **No change → no row.**

**Worked example (`maps.place` refresh):**
```
rating 4.4 → 4.3 (Δ0.1)    → code: < 0.2 → NOISE        (no LLM)
review_count 312 → 470     → code: ≥ 10 → MATERIAL      (no LLM)
hours unchanged            → no delta
description reworded        → code: no rule → ASK AGENT → NOISE
⇒ one Change row (review spike); one cheap LLM call; zero LLM on the rating tick.
```

### Refresh execution & idempotency — ride the invoking surface (no new run table)

`refresh(tracker)` is a **headless unit of work**; the run/audit record + idempotency live on **whatever
surface invoked it**:

- **Recurring (in-app):** invoked by the **CI automation action** (`06`) → the existing **`AutomationRun`**
  is the run record and the automations executor provides the **PENDING→running idempotency gate**. This is
  exactly the rigor old `06` hand-built — reused, not re-written.
- **Chat (manual / agent):** invoked via the chat **job record** (`04a`) + `deliverable_wait`.
- **Billing idempotency is per *capability call*, not per run:** each `executor` bills a success once via
  the billing service (`04a`); the content-hash pre-check (step 2) prevents needless re-crawls/charges. No
  run-level `charged_micros` ledger required for MVP.

Net: the only genuinely new state is the **Timeline** (`05a`); execution accounting is borrowed.

### User-supplied context files (the F idea, generalized)

When a user uploads a file *in a CI chat* (e.g. "our own price list"), it goes into the **KB as normal** —
uploads create `Document`s and are indexed/embedded, exactly as today. **(The "don't index" rule applies
only to *crawled* data.)** The CI-specific part is **organization + use**:

- **Routed to a dedicated folder** for that CI chat/Tracker (reuse the existing folder-upload machinery).
- **The judge step (5) may consult them** — retrieved from the KB, scoped to that folder:

```
competitor price 12.00 → 9.90   + user's context file says "our price is 10.00"
   → agent: competitor crossed *below our price* → MATERIAL (and explain why)
```

The user's private context **shapes what counts as material**. Reuses existing KB upload + folder +
retrieval machinery (nothing new). **MVP-optional** (the loop works without it); design the seam now.

### Where it lives / decoupling

- New **Apache-2** package `app/intelligence/` (schema-design agent, hot loop, materiality evaluator). Calls
  capability `executor`s directly.
- Exposes **`refresh(tracker)`**. *Who* calls it (manual / agent / external cron / optional automation) is
  the **Triggers** domain's concern (`06`) — Intelligence has **no dependency** on any scheduler.

## Work items

1. **Tracker model + persistence**: `decision` · `capability_binding` · versioned locked `definition` · `status`.
2. **Schema-design flow**: bind → sample-fetch → agent-drafts `definition` → human review/lock → version.
3. **Materiality evaluator**: deterministic rule engine (numeric/clear) + the agent-on-ambiguous fallback.
4. **The hot loop** `refresh(tracker)`: crawl → hash pre-check → fill → diff → judge → append (writes `05a`).
5. **Idempotency wiring**: ride `AutomationRun` (recurring) / chat job record (manual) — no new run table.
6. **Context-folder seam**: optional KB-retrieval hook into the judge, scoped to the Tracker's folder.

## Tests

- **Pre-check short-circuit**: identical content hash → no fill, no LLM, only `last_checked_at` bumped.
- **Fill conforms to lock**: extra observed fields land in `notable_signals`, never invent schema fields.
- **Materiality split**: numeric Δ over threshold → `decided_by=code, material`; ambiguous reword →
  `decided_by=agent`; sub-threshold → noise, no row.
- **Append semantics**: a material run writes one `entity_changes` row + overwrites current state.
- **Idempotency**: a redelivered recurring refresh (same `AutomationRun`) does not double-write or double-bill.
- **Context folder (optional)**: judge ruling flips when a user context file changes the decision frame.

## Risks / trade-offs

- **Refresh failure path** (capability returns `FAILED`/partial): skip vs retain vs retry vs alert — an
  implementation-time call (no architecture impact).
- **Agent fill cost** on changed pages: bounded by the hash pre-check; only changed content reaches the LLM.
- **Schema lock rigidity**: locking trades flexibility for run-to-run stability; re-lock creates a new version.

## Resolved decisions

1. `Tracker` is the standing-concern primitive; replaces "pipeline".
2. Stateless (`04`/Product A) vs stateful (`05`/Product B) is the Access→Intelligence boundary.
3. **Agent-designed schema flow is in MVP** (not hand-authored) — sample-grounded, human-locked, versioned.
4. Single entity per Tracker for MVP.
5. Materiality = deterministic numeric/clear rules in code + agent only on ambiguous.
6. Content-hash pre-check short-circuits unchanged pages before any LLM spend.
7. `app/intelligence/` Apache-2; `refresh(tracker)` is trigger-agnostic.
8. **No new run table** — refresh audit/idempotency ride `AutomationRun` (recurring) or the chat job record;
   billing idempotency is per-capability-call + the content-hash gate. Only Timeline (`05a`) is new state.
9. **CI context folder** (F): user files uploaded in a CI chat go into the **KB as normal** (indexed),
   routed to a dedicated `Folder`, and may feed the judge via KB retrieval. "Don't index" is for *crawled*
   data only. MVP-optional seam.

## Out of scope (hand-offs)

- **The state tables** (the three stores, content-hash, read API) → `05a`.
- **When refresh fires + recurrence/delivery** → `06` (Triggers).
- **The human-facing crafting/answering experience** (the `intelligence_agent` subagent + prompt) → `07`.
- **Schema auto-evolution**, multi-entity Trackers, backward-replay, coverage-confidence, the
  resale/data-product stage → north star (deferred).

## Open questions (carry forward)

- How the schema-design agent surfaces "review & lock" before the frontend exists (pure-chat confirmation?).
- Versioning policy on re-lock (new version vs in-place) — lean new version.
- Where the schema-design agent itself runs (a setup capability? a chat sub-flow?).
- Context-folder → judge wiring (how much to load; per-Tracker vs per-chat scope).
