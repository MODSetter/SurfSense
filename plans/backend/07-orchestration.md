# Phase 7 — Orchestration / Conversation (the CI-expert subagent)

> **Status (2026-07-02): shipped for the web verbs.** The `scraping` subagent, its tools, prompt, and
> router blurb are live; `web.discover`/`web.scrape` compose and the "keep watching" handoff (`06`) is
> wired. `maps.*` composition is deferred until the Maps actor exists.
> Sits atop `04`/`05` (and `06` for the ongoing mode). The multi-agent chat runtime (deepagents, subagent
> dispatch, streaming, citation middleware) is shipped. Net-new here = one builtin subagent + its tools +
> its prompt. Locate code by symbol/grep.

## Objective

Ship the `scraping` subagent — a builtin CI/scraper-expert that delivers the product through
plain conversation: understand intent, compose scraper verbs (`04`), answer in plain language, and hand
standing needs to the ongoing "keep watching" mode (`06`). It reasons over chat history to report what's
new vs prior tool outputs already in context.

## The subagent

Builtin `subagents/builtins/scraping/`, peer to `research`/`deliverables`, packed via
`pack_subagent`. Files follow the existing pattern: `agent.py` (`build_subagent`), `tools/index.py`
(`NAME · RULESET · load_tools`), `description.md` (router one-liner), `system_prompt.md` (the playbook).
The main agent delegates CI-/scraping-flavored requests to it via `description.md`.

## The playbook (`system_prompt.md`)

1. **Intent routing** — one-shot ("compare/find/what is") → compose verbs & answer; standing concern
   ("watch/track/notify when/weekly") → hand to `06`; ambiguous → ask one question ("just once, or keep
   watching?").
2. **Verb composition** — chains `web.discover → web.scrape` and `maps.search → maps.place → maps.reviews`;
   infer URLs/queries/locations from context.
3. **"What changed"** — re-invoke the verb and compare against prior tool outputs in the chat history,
   summarizing what's new.

## The toolset (`load_tools`)

| Tool | Wraps | Billing |
|------|-------|---------|
| capability verbs — `web.scrape`, `web.discover` shipped; `maps.search`/`maps.place`/`maps.reviews` deferred (Maps actor) | `04` executors (direct-return) | `03c` owner-wallet charge via `charge_capability` (same path as REST/MCP) |
| `start_watch` / `stop_watch` / `refresh_watch` | bind a watch to the current chat via `06` | per re-invocation |

Verbs reach the subagent through the chat door generator `access/chat.py::build_capability_tools` (`05`),
which turns registry verbs (`04`) into tools with owner-wallet billing. The `scraping` subagent owns these
CI-flavored calls; the main agent's `web_search`/`scrape_webpage` stay untouched.

## Boundaries

- The subagent drives the `04` verbs via tools; fetch/bypass/clean logic stays in Acquisition + `04`,
  callable headless.
- Humans get the agent; REST/MCP callers call `04` verbs directly, skipping this subagent.

## Work items

1. **[done]** Subagent scaffold: `subagents/builtins/scraping/` (`agent.py` / `tools/index.py` /
   `description.md` / `system_prompt.md`), packed via `pack_subagent`.
2. **[done]** CI playbook prompt: intent routing (block on ambiguous cadence), verb chains, "what changed" reasoning.
3. **[done]** Chat door generator: `access/chat.py::build_capability_tools` turns registry verbs (`04`) into tools (`05`).
4. **[done]** `start_watch` / `stop_watch` / `refresh_watch` seam to `06`, bound to the current chat.
5. **[done]** Router registration: `description.md` for main-agent delegation.

## Tests

- A CI-/scraping-flavored request routes to `scraping`; a non-CI request does not.
- "compare X and Y" composes verbs and answers in plain language, persisting nothing.
- "reviews for the top 3 coffee shops near me" chains `maps.search → maps.place → maps.reviews`.
- A follow-up re-invokes the verb and reports new items vs prior in-context outputs.
- "watch this weekly" routes to the ongoing mode, not a one-shot answer.

## Out of scope

- Verbs, doors → `04`/`05`. Ongoing/periodic mechanism → `06`.
- Richer multi-step playbooks, proactive suggestions, cross-topic synthesis.
- Frontend CI surfaces → frontend umbrella.

## Open questions

- None outstanding for the web verbs. `maps.*` composition reopens when the Maps actor lands.
