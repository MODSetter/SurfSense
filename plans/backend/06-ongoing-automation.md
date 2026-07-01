# Phase 6 — Ongoing Automation (chat-native "keep watching")

> **Design deferred — placeholder.** The mechanism is designed separately, after `04`/`05`/`07`.
> Depends on `04` (the verbs it re-invokes) and `05` (the chat surface + delivery channel).

## Objective

Support "keep watching": a persistent, ongoing chat where the agent periodically re-invokes scraper verbs
and drops results into the session. The agent derives what's new by reading the chat history (time-based
search over prior tool outputs in context).

## Open design questions (resolve together)

1. **Periodicity driver** — the existing automations schedule selector, a recurring task, or a persistent
   agent loop.
2. **Delivery channel** for between-turn results — existing SSE stream vs a Zero-published messages table.
3. **Context-window limit** — how far back "what changed" can reason before summarization/compaction.
4. **Loop owner** — the `07` subagent, or a thin automation wrapper that invokes the agent.
5. **Stop / pause / cost controls** for a running watch.

## Out of scope

- The verbs → `04`. The chat surface + delivery → `05`. The agent playbook → `07`.

> Next step: design the periodic mechanism here, then fill in Target design / Work items / Tests.
