# Phase 7 — Orchestration / Conversation (the CI-expert subagent)

> **Phase 7** of the CI-pivot revamp — the **human-facing brain** that turns "natural language is the only
> surface" (`04b`, Decision 0) into a real deliverable. **Build last** — it sits atop `04`–`06`.
> **Depends on** all prior phases: `04a` verbs, `04b` doors + `deliverable_wait`, `05a`/`05b` Tracker +
> Timeline, `06` refresh triggers.
> **Scope guardrail:** the multi-agent chat **runtime** (deepagents, subagent dispatch, streaming,
> citation middleware, `deliverable_wait`) is SHIPPED/FIXED. What's **net-new here** is one builtin
> subagent + its tools + its prompt. We *plug into* the runtime; we don't rebuild it.

## Objective

Ship the **`intelligence_agent`** — a net-new builtin CI-expert subagent — so users get the whole product
through plain conversation: intent routing (one-shot vs standing concern), verb composition, Tracker
crafting, and decision-grounded answering. The intent router + verb-composition + Tracker-crafting are
where "user-friendly" is won or lost, so the orchestration layer is **designed, not assumed**.

## Current state (cited)

- **Builtin subagent pattern** — `subagents/builtins/<name>/`: `agent.py` (`build_subagent(...)` →
  `pack_subagent(name, description, system_prompt, tools, ruleset, …)`), `tools/index.py`
  (`NAME · RULESET · load_tools(dependencies)`), `description.md` (router one-liner), `system_prompt.md`
  (the playbook), optional middleware (e.g. `citation_state`). Peers: `research`, `deliverables`.
- **Tool shape** — `research/tools/scrape_webpage.py` shows the **tool = capability executor + access door**
  pattern (calls `WebCrawlerConnector.crawl_url`, returns a typed dict). **Billing note:** its current
  `get_current_accumulator()` fold is **interactive-chat-only** and no-ops outside a chat turn — so CI tools
  do **not** copy that as the charging path. Per `04a` (locked), **the charge fires in the capability
  executor**; the chat turn accumulator stays only as an optional presentation fold. This is what makes the
  recurring `06 → refresh → verb → crawl` path (no chat turn) bill correctly.
- **Slow-job path** — `deliverable_wait` poll-until-terminal + the podcast-style live card (`04b`).

## Target design

### The `intelligence_agent` subagent (CI expert)

A new builtin `subagents/builtins/intelligence_agent/` (the competitive-intelligence specialist), peer to
`research`/`deliverables`. The **main agent delegates** to it whenever the request is CI-flavored (research
a competitor, watch something, analyze a place's reviews); `description.md` is what makes that routing
happen. It owns the **CI playbook** in `system_prompt.md`:

1. **Intent routing (A vs B)** — the Decision-0 rule, in-prompt: one-shot ("compare/find/what is") → call
   verbs & answer; standing concern ("watch/track/notify when/weekly") → run the crafting flow; ambiguous →
   ask the single clarifying question.
2. **Verb composition** — the chains: `web.discover → web.scrape`, `maps.search → maps.place →
   maps.reviews`; infer URLs/queries/locations from context so the user never supplies them by hand.
3. **Tracker crafting** — the conversational schema-design flow from `05b`: sample-fetch → propose
   `field_schema` + materiality + identity → user validates & locks → versioned.
4. **Decision-grounded answering** — read the Timeline (`05a`) to answer "what changed / is X pulling
   ahead?" from stored deltas, not by re-deriving from chat history.

### The toolset (what `load_tools` returns)

| Tool | Wraps | Mode | Billing |
|------|-------|------|---------|
| capability verbs (`web.scrape`, `web.discover`, `maps.search`, `maps.place`, `maps.reviews`) | `04a` executors | inline-or-job (slow → `deliverable_wait`) | at the `04a` executor (per-call); chat turn accumulator = optional presentation fold only |
| `craft_tracker(decision, binding)` | `05b` schema-design agent | inline (sample-fetch + proposes) | sample crawl billed |
| `lock_tracker(draft)` / `update_tracker` | `05b` Tracker persistence | inline | — |
| `refresh_tracker(tracker_id)` | `05b` `refresh(tracker)` (via `06`) | job → `deliverable_wait` | per capability call |
| `query_timeline(tracker_id, …)` | `05a` read API | inline | — |
| `list_trackers()` | `05a`/`05b` read | inline | — |

- **Capability verbs are a shared tool module** (generated from the `04a` registry) — `research` can load
  the same ones; the `intelligence_agent` additionally loads the Tracker/Timeline tools + the CI prompt.
  (`scrape_webpage` is the seed; generalize it into the registry-backed set.)
- **Slow verbs** (`maps.search`, multi-URL `web.scrape`, `refresh_tracker`) dispatch a job and use the
  existing `deliverable_wait` poll-until-terminal + live-card path (`04b`).

### Boundaries

- **Orchestration ≠ Intelligence.** The `intelligence_agent` *drives* `05a`/`05b` via tools; the hot loop,
  materiality, and Timeline writes live in `05a`/`05b`, callable headless (so REST/MCP and Triggers reach the
  same logic with no agent in the loop).
- **Humans get the agent; machines get raw verbs.** REST/MCP callers (devs/external agents) skip this
  subagent entirely and call `04a` verbs directly — they *want* explicitness.

## Work items

1. **Subagent scaffold**: `subagents/builtins/intelligence_agent/` with `agent.py` / `tools/index.py` /
   `description.md` / `system_prompt.md`, packed via `pack_subagent`.
2. **CI playbook prompt**: intent routing (A/B + one clarifying question), verb chains, crafting flow,
   decision-grounded answering.
3. **Shared verb tool module**: registry-backed (`04a`) capability tools, reusable by `research` too.
4. **Tracker/Timeline tools**: `craft_tracker` / `lock_tracker` / `update_tracker` / `refresh_tracker` /
   `query_timeline` / `list_trackers`.
5. **Slow-verb wiring**: route job-mode tools through `deliverable_wait` + the live card.
6. **Router registration**: `description.md` so the main agent delegates CI-flavored requests here.

## Tests

- **Delegation**: a CI-flavored request routes to `intelligence_agent`; a non-CI request does not.
- **One-shot**: "compare X and Y" composes verbs and answers in plain language, persisting nothing.
- **Standing concern**: "watch X weekly" runs the crafting flow → lock → (refresh via `06`).
- **Crafting**: `craft_tracker` does a real sample-fetch and proposes a schema; `lock_tracker` versions it.
- **Answering**: `query_timeline` answers "what changed?" from stored deltas, not chat history.
- **Slow verb**: a multi-URL scrape surfaces a live card and returns terminal results.

## Risks / trade-offs

- **Prompt quality is the product**: intent-router/composition quality is a first-class deliverable, not
  plumbing — budget iteration on the prompt.
- **One-shot ownership**: whether `research` keeps generic scraping or the `intelligence_agent` owns all
  CI-flavored calls (lean: shared verb tools, CI agent owns the *playbook*).
- **Pre-frontend lock UX**: "review & lock" must render in pure chat for MVP (ties to `05b`'s open Q).

## Resolved decisions

1. CI orchestration is a **net-new builtin subagent** (`intelligence_agent`) on the existing runtime — not
   a runtime rebuild.
2. Tools follow the `scrape_webpage` executor+door shape, but **billing fires in the `04a` executor** (not the chat turn accumulator, which is interactive-only and would skip automation/cron runs).
3. Capability verbs are a **shared, registry-generated** tool module; the `intelligence_agent` adds
   Tracker/Timeline tools + the CI prompt.
4. Intent routing (A vs B) lives **in the subagent prompt**; the headless logic stays in `05a`/`05b`.
5. Slow verbs reuse `deliverable_wait`; nothing new for chat-async.

## Out of scope (hand-offs)

- **The verbs, doors, engine, state, and triggers** → `04`/`05`/`06` (this phase only *orchestrates* them).
- **Richer multi-step CI playbooks** (auto competitor discovery → multi-Tracker setup), proactive "you
  should watch this" suggestions, cross-Tracker synthesis → north star (deferred).
- **Frontend CI surfaces** (cards, dashboards) → frontend umbrella.

## Open questions (carry forward)

- Does CI one-shot scraping stay in `research`, or does the `intelligence_agent` own all CI-flavored calls
  (lean: shared verb tools, `intelligence_agent` owns the *CI playbook*).
- How `craft_tracker`'s "review & lock" renders pre-frontend (pure-chat confirmation — ties to `05b`'s open Q).
