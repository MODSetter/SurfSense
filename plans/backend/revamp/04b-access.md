# Phase 4b — Access / Surfaces (chat · REST · MCP doors)

> Part of **Phase 4 — Capabilities & Access**. Sits on top of `04a-capabilities.md` (the registry it exposes).
> **Build after** `04a`. Together, `04a + 04b` ship **Product A** (stateless utility) — revenue day one.
> **Depends on** SHIPPED infra: Identity/Tenancy, **API keys**, the chat agent + its tool registry, the
> streaming layer, and Metering (`03c`). Access *reuses* them — it builds none net-new.
> **Scope guardrail:** Phases 1–3 SHIPPED/FIXED. Locate code by **symbol/grep**, not the cited lines.

## Objective

Expose the capability registry (`04a`) to callers, **authenticated + metered**, through three doors —
**chat tools, REST + API keys, MCP server** — all **generated from the one registry** so the I/O
contract cannot drift between surfaces. Access contains **no business logic**: every door is the same
thin adapter.

## Current state (cited)

- **API keys** — existing per-workspace key infra (reuse; do **not** build net-new); billed to the
  workspace owner via `03c`.
- **Chat agent + tool registry** — capability tools register *into* the existing registry; the seed is
  `research/tools/scrape_webpage.py` (capability executor + access door + `03c` turn-accumulator billing).
- **Slow-job pattern** — `subagents/builtins/deliverables/deliverable_wait.py`: dispatch a Celery task,
  poll the row's `status` until `READY`/`FAILED` (1.5s cadence), bounded by
  `SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS` (default 300s); `deliverables/tools/podcast.py` is the
  "return now + live card tracks progress" model.
- **BYO-`MCP_CONNECTOR`** (old `04a`) — the user's own external MCP tools inside our chat agent; its
  routing-map gap is the one "connector" worth fixing, and it lands **here**.

## Target design

### The adapter shape (identical on every door)

```
parse input → validate against verb.input_schema → authn/authz → meter-gate (03c)
  → call the SAME executor (04a) → serialize verb.output_schema → return the uniform envelope
```

### The three doors (locked order: chat → REST → MCP)

| Door | Who | Auth | Status |
|------|-----|------|--------|
| **Chat tools** | in-app agent (Product B delivery + interactive) | existing session + workspace | partly exists (`scrape_webpage`) |
| **REST + API keys** | external developers (Product A) | **existing API-key infra** | **public day one** |
| **MCP server** | external agents (Cursor/ChatGPT/Claude) | OAuth 2.1 **or** bearer — chosen at implementation | **fast-follow** |

REST being public day one is cheap precisely because the routes are **generated**, not hand-written —
it's a go-to-market choice, not an engineering cost.

### Natural language is THE surface (verbs are internal) — non-negotiable

The human-facing product is **the conversation**. A user **never** names a verb, fills an `input_schema`,
or knows "Product A vs B" exists — they describe a *need* in plain language and the agent does the rest.
Raw typed verbs are exposed only on the REST/MCP doors (devs/external agents). The chat agent owns three
responsibilities per message: **understand intent** → **pick & fill verbs** (incl. chains like
`discover → scrape`, `search → place → reviews`) → **answer in plain language** (results, not envelopes).

### The intent router (the one new orchestration rule)

The agent classifies each request along the stateless/stateful line **from the language**:

```
"compare / find / what is / pull / summarize / right now"               → ONE-SHOT  → call verbs, answer  (Product A, stateless)
"watch / track / notify me when / every week / keep an eye / over time" → STANDING  → start Tracker setup (Product B, stateful → 05b)
ambiguous → ask ONE question: "just this once, or should I keep watching it for you?"
```

This router is the friendly seam between the two products; it lives in the chat door (its prompt lives
in the `intelligence_agent`, `07`) and is the only human-facing decision point.

### The two MCP directions (keep distinct)

- **We *serve* MCP** — our capabilities as a remote MCP server (door #3, new): Streamable-HTTP `/mcp`,
  stateless, bounded/paginated outputs, untrusted inputs, least-privilege (read-only verbs).
- **We *consume* MCP** — the BYO-`MCP_CONNECTOR` (old 04a): the user's own external MCP tools inside our
  chat agent. The 04a routing-gap fix lands **here**, not in Capabilities.

### Chat ↔ slow jobs — reuse the existing background-worker pattern

Do **not** invent a chat-async mechanism. A slow verb (`web.scrape` over many URLs, `maps.search`,
`maps.reviews`) invoked from chat dispatches the **job** (the `04a` job record) and uses the
`deliverable_wait` poll-until-terminal path; the capability **job record's `status`** is what the helper
polls. Most calls finish inside the poll window → results inline; genuinely long ones surface a tracked
card. REST/MCP expose the same job via `GET /v1/jobs/{id}` (and an MCP equivalent).

## Work items

1. **Door generator**: from the `04a` registry, emit (a) chat tool defs + handlers, (b) REST routes +
   request/response models, (c) MCP tool schemas + handlers — one adapter shape.
2. **REST surface**: public routes + API-key auth (reuse existing) + the `03c` meter-gate; `GET /v1/jobs/{id}`.
3. **Chat tools**: generalize `scrape_webpage` into the registry-backed set; wire slow verbs through
   `deliverable_wait` polling the `04a` job record's `status`.
4. **Intent router**: the A-vs-B classifier (its home is the `07` subagent prompt; the seam is here).
5. **MCP server (fast-follow)**: Streamable-HTTP `/mcp`, least-privilege; auth depth chosen at implementation.
6. **Consume-MCP fix**: repair the BYO-`MCP_CONNECTOR` routing-map gap (old 04a).

## Tests

- **Generated parity**: a verb added to the registry appears on chat + REST (+ MCP) with identical I/O.
- **Auth + meter**: REST without a valid key → 401; an over-budget call → blocked by the `03c` gate
  before execute; a success charges once.
- **Chat slow verb**: a many-URL `web.scrape` returns inline when fast; surfaces a tracked card when long;
  `GET /v1/jobs/{id}` reflects the same terminal status.
- **Intent router**: "compare X and Y" → one-shot; "watch X weekly" → Tracker setup handoff; ambiguous →
  exactly one clarifying question.
- **Consume-MCP**: a configured BYO MCP tool is reachable by the chat agent (routing-gap closed).

## Risks / trade-offs

- **Public REST day one** → needs bounded inputs + per-key quotas / abuse posture (design alongside launch).
- **MCP auth depth** deferred to implementation (OAuth 2.1 vs bearer) — don't over-build before a consumer exists.
- **Serve-vs-consume MCP confusion** — keep the two directions explicitly separate in code and docs.

## Resolved decisions

0. **Natural language is the only human-facing surface.** Users never name verbs/schemas/jobs; the chat
   agent understands intent, picks & fills verbs, answers in plain language; an intent router classifies
   one-shot (A) vs standing-concern (B), asking one question only when ambiguous. Raw verbs live only on REST/MCP.
1. Three doors, generated from the capability registry; order chat → REST → MCP.
2. REST is **public day one** (cheap; go-to-market choice).
3. API keys: **reuse existing infra**, billed to workspace owner.
4. MCP server is a **fast-follow**; auth depth (OAuth 2.1 vs bearer) chosen at implementation.
5. Chat ↔ slow jobs: **reuse `deliverable_wait` poll-until-terminal + live card**, polling the `04a` job record's `status`.
6. "Serve MCP" (our tools out) vs "consume MCP" (BYO tools in) are distinct; the old-04a fix is the consume side.

## Out of scope (hand-offs)

- **The verbs themselves** (executors, registry, billing units) → `04a`.
- **The CI subagent + its prompt/playbook** (where the intent router actually lives) → `07`.
- **Stateful flows** (Tracker crafting, refresh, timeline reads) → `05b`/`05a`, surfaced via chat tools in `07`.
- Legacy branded connectors stay only for backward-compat (separate hygiene task).

## Open questions (carry forward)

- MCP auth depth (decide at implementation).
- Public REST rate-limiting / abuse posture (bounded inputs, per-key quotas).
- Whether `web.discover` is metered or free (carried from `04a`).
