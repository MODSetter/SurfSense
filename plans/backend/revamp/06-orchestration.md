# Domain ⑥ — Orchestration / Conversation (the CI-expert subagent) (CI pivot revamp · WIP)

> **WIP design doc.** Part of the Phase 4 → end revamp. This is the **human-facing brain** that turns
> Decision-0 ("natural language is the only surface", `02-access.md`) into a real deliverable.
> **Scope guardrail:** the multi-agent chat **runtime** (deepagents, subagent dispatch, streaming,
> citation middleware, `deliverable_wait`) is SHIPPED/FIXED. What's **net-new here** is one builtin
> subagent + its tools + its prompt. We *plug into* the runtime; we don't rebuild it.

## Why this is a first-class deliverable

The intent router + verb-composition + Lens-crafting are where "user-friendly" is won or lost. Treating
the agent prompt/tooling as plumbing would make the product feel rigid. So the orchestration layer gets
designed, not assumed.

## The pattern we reuse (verbatim)

Builtin subagents live at `subagents/builtins/<name>/`:
```
agent.py            build_subagent(...) → pack_subagent(name, description, system_prompt, tools, ruleset, …)
tools/index.py      NAME · RULESET · load_tools(dependencies)
description.md      one-liner the router uses to delegate
system_prompt.md    the playbook
(middleware)        e.g. citation_state
```
`research/tools/scrape_webpage.py` already shows the **tool = capability executor + access door + 03c
billing** shape: it calls `WebCrawlerConnector.crawl_url`, bills via the turn accumulator
(`get_current_accumulator()` + `WebCrawlCreditService`), returns a typed dict. Our capability/CI tools
follow this exactly.

## What's new — the `analyst` subagent (CI expert)

A new builtin `subagents/builtins/analyst/` (working name — the competitive-intelligence specialist),
peer to `research`/`deliverables`. The **main agent delegates** to it whenever the request is
CI-flavored (research a competitor, watch something, analyze a place's reviews); `description.md` is
what makes that routing happen.

It owns the **CI playbook** in `system_prompt.md`:

1. **Intent routing (A vs B)** — the Decision-0 rule, in-prompt: one-shot ("compare/find/what is")
   → call verbs & answer; standing concern ("watch/track/notify when/weekly") → run the crafting flow;
   ambiguous → ask the single clarifying question.
2. **Verb composition** — the chains: `web.discover → web.scrape`, `maps.search → maps.place →
   maps.reviews`; infer URLs/queries/locations from context so the user never supplies them by hand.
3. **Lens crafting** (the "crafting" you flagged) — the conversational schema-design flow from `03`:
   sample-fetch → propose `field_schema` + materiality + identity → user validates & locks → versioned.
4. **Decision-grounded answering** — read the Timeline (`04`) to answer "what changed / is X pulling
   ahead?" from stored deltas, not by re-deriving from chat history.

## The toolset (what `load_tools` returns)

| Tool | Wraps | Mode | Billing |
|------|-------|------|---------|
| capability verbs (`web.scrape`, `web.discover`, `maps.search`, `maps.place`, `maps.reviews`) | Domain ① executors | inline-or-job (slow → `deliverable_wait`) | `03c` turn accumulator (as `scrape_webpage` already does) |
| `craft_lens(decision, binding)` | `03` schema-design agent | inline (does the sample-fetch + proposes) | sample crawl billed |
| `lock_lens(draft)` / `update_lens` | `03` Lens persistence | inline | — |
| `refresh_lens(lens_id)` | `03` `refresh(lens)` | job → `deliverable_wait` | per capability call |
| `query_timeline(lens_id, …)` | `04` read API | inline | — |
| `list_lenses()` | `04`/`03` read | inline | — |

- **Capability verbs are a shared tool module** (generated from the Domain ① registry) — `research`
  can load the same ones; the `analyst` additionally loads the Lens/Timeline tools + the CI prompt.
  (`scrape_webpage` is the seed; generalize it into the registry-backed set.)
- **Slow verbs** (`maps.search`, multi-URL `web.scrape`, `refresh_lens`) dispatch a job and use the
  existing `deliverable_wait` poll-until-terminal + live-card path (`02-access.md`).

## Boundaries

- **Orchestration ≠ Intelligence.** The `analyst` *drives* `03`/`04` via tools; the hot loop,
  materiality, and Timeline writes live in `03`/`04`, callable headless (so REST/MCP and Triggers reach
  the same logic with no agent in the loop).
- **Humans get the agent; machines get raw verbs.** REST/MCP callers (devs/external agents) skip this
  subagent entirely and call Domain ① verbs directly — they *want* explicitness.

## MVP cut vs north star

- **MVP:** the `analyst` subagent + description/prompt · capability verb tools (registry-backed) ·
  `craft_lens`/`lock_lens`/`refresh_lens`/`query_timeline`/`list_lenses` · intent routing in-prompt.
- **North star (deferred):** richer multi-step CI playbooks (auto competitor discovery → multi-Lens
  setup), proactive "you should watch this" suggestions, cross-Lens synthesis.

## Locked decisions

1. CI orchestration is a **net-new builtin subagent** (`analyst`, working name) on the existing
   runtime — not a runtime rebuild.
2. Tools follow the `scrape_webpage` shape: capability executor + access door + `03c` billing.
3. Capability verbs are a **shared, registry-generated** tool module; the `analyst` adds Lens/Timeline
   tools + the CI prompt.
4. Intent routing (A vs B) lives **in the subagent prompt**; the headless logic stays in `03`/`04`.
5. Slow verbs reuse `deliverable_wait`; nothing new for chat-async.

## Open questions (carry forward)

- Subagent **name/persona** (`analyst`? `intelligence`? `scout`?).
- Does CI one-shot scraping stay in `research`, or does the `analyst` own all CI-flavored calls (lean:
  shared verb tools, `analyst` owns the *CI playbook*).
- How `craft_lens`'s "review & lock" renders pre-frontend (pure-chat confirmation — ties to `03`'s open Q).
