# Domain ② — Access / Surfaces (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp. Sits on top of Domain ① (Capabilities).
> **Scope guardrail:** Phases 1–3 are SHIPPED and FIXED. Identity/Tenancy, API keys, the chat
> agent + its tool registry, the streaming layer, and Metering (`03c`) already exist — Access
> *reuses* them.

## Role in the universe

```
FIXED:   Acquisition · Metering (03c) · Identity/Tenancy · API keys · chat agent · streaming
SCOPE:   Capabilities → ▶ Access ◀ → Intelligence + Timeline → Triggers
```

Access is the set of **doors** onto the capability registry. It contains **no business logic** —
every door is the same thin adapter.

## Purpose

Expose the capability registry to callers, **authenticated + metered**. One adapter shape for every
verb, on every door:

```
parse input → validate against verb.input_schema → authn/authz → meter-gate (03c)
  → call the SAME executor → serialize verb.output_schema → return the uniform envelope
```

## The three doors (locked order: chat → REST → MCP)

| Door | Who | Auth | Status |
|------|-----|------|--------|
| **Chat tools** | in-app agent (Product B delivery + interactive) | existing session + workspace | partly exists (`scrape_webpage`) |
| **REST + API keys** | external developers (Product A) | **existing API-key infra** (reuse, do not build net-new) | **public day one** |
| **MCP server** | external agents (Cursor/ChatGPT/Claude) | OAuth 2.1 **or** bearer — *chosen at implementation* | **fast-follow** after chat+REST |

All three are **generated from the one capability registry** (Domain ①). REST being public day one
is cheap precisely because the routes are generated, not hand-written — it's a go-to-market choice,
not an engineering cost.

## Natural language is THE surface (verbs are internal) — non-negotiable

The human-facing product is **the conversation**. A user **never** names a verb, fills an
`input_schema`, or knows "Product A vs B" exists — they describe a *need* or a *worry* in plain
language and the agent does the rest. Verbs/schemas/jobs/deltas are things the agent manages **on the
user's behalf**. (The raw typed verbs are exposed only on the REST/MCP doors, which serve
**developers/external agents**, not humans — that's the whole reason those doors exist separately.)

The chat agent therefore owns three responsibilities on every message:

1. **Understand intent** (what does the user actually want?).
2. **Pick & fill the verbs** — infer URLs / queries / locations / place refs from the conversation and
   compose one or more capability calls (incl. the natural chains, e.g.
   `discover → scrape`, `search → place → reviews`).
3. **Answer in plain language** (results, not envelopes).

### The intent router (the one new orchestration rule)

The agent classifies each request along the stateless/stateful line **from the language**, so the
user never has to:

```
"compare / find / what is / pull / summarize / right now"      → ONE-SHOT  → call verbs, answer        (Product A, stateless)
"watch / track / notify me when / every week / keep an eye / over time" → STANDING → start the Tracker setup flow (Product B, stateful → ③)
```

- **One-shot** → orchestrate verbs now, synthesize an answer; nothing persists beyond chat.
- **Standing concern** → hand off to the Intelligence setup flow (`03`): sample-fetch → agent proposes
  schema/thresholds/identity → user validates & locks → Tracker runs on a trigger.
- **Ambiguous** → ask exactly **one** clarifying question — *"just this once, or should I keep watching
  it for you?"* — which is the entire A-vs-B decision expressed in human terms.

This router is the friendly seam between the two products; it lives in the chat door and is the only
human-facing decision point.

## The two MCP directions (keep distinct)

- **We *serve* MCP** — our capabilities as a remote MCP server (door #3, new). "External agents gain
  the real web." Remote Streamable-HTTP `/mcp`, stateless, bounded/paginated outputs, untrusted
  inputs, least-privilege (read-only verbs). Auth depth decided at implementation.
- **We *consume* MCP** — the BYO-`MCP_CONNECTOR` from old 04a: the user's *own* external MCP tools
  inside our chat agent. This is the only "connector" worth keeping; the 04a routing-gap fix lands
  **here** (Access/Conversation), not in Capabilities.

## Chat ↔ slow jobs — reuse the existing background-worker pattern

Do **not** invent a chat-async mechanism. The deliverables stack already solves it:

- `subagents/builtins/deliverables/deliverable_wait.py` — a shared **poll-until-terminal** helper:
  dispatch the Celery task, poll the row's `status` until `READY`/`FAILED` (1.5s cadence), return a
  real terminal outcome. Bounded by `SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS` (default 300s) in
  multi-agent mode.
- `deliverables/tools/podcast.py` — the "return now + a live card tracks progress" model for very
  long work; streaming emission frames live under
  `tasks/chat/streaming/handlers/tools/deliverables/...`.

**Mapping to capabilities:** a slow verb (`web.scrape` over many URLs, `maps.search`, `maps.reviews`)
invoked from chat dispatches the **job** (Domain ① job record) and uses the `deliverable_wait`
poll-until-terminal path; the capability **job record's `status`** is what the helper polls (the
analogue of the podcast/artifact status row). Most calls finish inside the poll window → the tool
returns results inline; genuinely long ones surface a tracked card. REST/MCP doors expose the same
job via `GET /v1/jobs/{id}` (and an MCP equivalent).

## Reused / fixed (not built here)

- **API keys** — existing infra; keys scope to a workspace; billed to the workspace owner via `03c`.
- **Identity & Tenancy** — workspace/user/permission checks on every door.
- **Chat agent + tool registry** — capability tools are *registered into* the existing registry.
- **Streaming layer** — existing SSE/card emission for chat job progress.
- **Metering (`03c`)** — the balance gate before execute + charge after, on every door.

## Relationship to the drafted Phase 4

- **04a BYO-`MCP_CONNECTOR` routing fix** → lands here (we *consume* the user's MCP tools).
- Old connector-config routes for data sources are **not** the surface anymore — the capability
  REST/MCP/chat doors are. Legacy branded connectors stay only for backward-compat (separate
  hygiene task).

## Locked decisions

0. **Natural language is the only human-facing surface.** Users never name verbs/schemas/jobs; the
   chat agent understands intent, picks & fills verbs, and answers in plain language. An **intent
   router** classifies one-shot (Product A) vs standing-concern (Product B) from the language, asking
   one clarifying question only when ambiguous. Raw verbs are exposed solely on REST/MCP (dev/agent
   doors).
1. Three doors, generated from the capability registry; order chat → REST → MCP.
2. REST is **public day one** (cheap; go-to-market choice).
3. API keys: **reuse existing infra**, billed to workspace owner.
4. MCP server is a **fast-follow**; auth depth (OAuth 2.1 vs bearer) chosen at implementation.
5. Chat ↔ slow jobs: **reuse `deliverable_wait` poll-until-terminal + live card**, polling the
   capability job record's `status`.
6. "Serve MCP" (our tools out) vs "consume MCP" (BYO tools in) are distinct; the 04a fix is the
   consume side.

## Open questions (carry forward)

- MCP auth depth (decide at implementation).
- Public REST rate-limiting / abuse posture (bounded inputs, per-key quotas) — design alongside the
  public launch.
- Whether `web.discover` is metered or free (carried from Domain ①).
