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

## Open questions (carry forward)

- How the schema-design agent surfaces the "review & lock" step before the frontend exists (pure-chat
  confirmation for MVP?).
- Versioning policy on re-lock (new version vs in-place) — lean new version.
- Where the schema-design agent itself runs (a setup capability? a chat sub-flow?).
