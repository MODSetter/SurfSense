# Phase 6 — Ongoing Automation (chat-native "keep watching")

> Depends on `04` (the verbs it re-invokes), `05` (the agent tools), and `07` (the `scraping` subagent).
> Reuses the existing chat + automations machinery; adds no parallel engine.

## Objective

Support "keep watching": a persistent chat where the agent periodically re-invokes scraper verbs and drops
results into the session. "What changed" is the agent reading its own prior turns from the durable
checkpoint — no diff store.

## Mechanism

A **chat watch is an `Automation` bound to the current chat** — nothing more. No dedicated thread, no
thread "kind", no schema change. Start it and the chat gains a `schedule` trigger that re-posts the
question on a cadence; stop it and the automation is deleted and the chat is a normal chat again. The
chat's own checkpoint is the memory.

- **`chat_message` action** — params `{ thread_id, message }`. Its handler drains
  `stream_new_chat(user_query=message, chat_id=thread_id, …)` under `AuthContext.system(creator,
  source="automation")` against the **current chat**. Auto-approve (system auth; CI verbs are read-only
  and don't interrupt).
- **Durable memory + delivery** — `stream_new_chat` persists messages to `new_chat_messages` (already
  Zero-synced to the UI) and advances the shared Postgres checkpointer keyed by `chat_id`. A scheduled run
  has no SSE client; it runs server-side and is delivered via the persisted rows. "What changed" is the
  agent reading the chat's own prior turns.
- **Worker-safe checkpointer** — the shared `AsyncPostgresSaver` pool binds connections to the loop that
  opened them, but Celery uses a fresh loop per task (`PoolTimeout`). Dispose the checkpointer pool per
  task in `run_async_celery_task`, mirroring `_dispose_shared_db_engine`, so a worker can use the *durable*
  checkpointer (not `InMemorySaver`) that "what changed" requires.
- **`start_watch`** — a `scraping` subagent tool that binds a watch to the *current* chat: it distills
  the recurring question + cadence and creates the automation (`schedule` + `chat_message(thread_id =
  current chat)`).
- **"Is this chat watched?"** — derived: an active automation with a `chat_message` action targeting the
  chat. No stored flag.
- **Controls** — run-now = trigger a run; stop = delete the automation (chat reverts to normal).
- **Concurrency** — the checkpointer is single-writer per thread; a tick skips if the prior turn on that
  chat is still running (DB `ai_responding` flag).

## Work items

1. Durable checkpointer in workers: `_dispose_shared_checkpointer_pool` in `run_async_celery_task`
   (before + after), mirroring the SQLAlchemy engine dispose. **[done]**
2. `chat_message` action: params + factory + handler (drains `stream_new_chat`); concurrency guard. **[done]**
3. Watch service: create (bind `schedule` + `chat_message` automation to a chat) / stop (delete) /
   find-for-thread (is-watched) / run-now. **[done]**
4. `start_watch` tool on the `scraping` subagent (+ prompt line); binds to the current chat. **[done]**
5. Controls — chat tools (`stop_watch`, `refresh_watch`) + REST (`GET /automations/watches`,
   `POST /automations/{id}/run`; stop = `DELETE /automations/{id}`). **[done]**

## Tests

- `run_async_celery_task` disposes the checkpointer pool before and after a task. **[done]**
- `chat_message` drains a turn on the given thread; skips when one is in-flight. **[done]**
- Watch service: create binds a `schedule` + `chat_message` automation to the chat; stop deletes it;
  find-for-thread filters by plan; run-now launches the schedule trigger. **[done]**
- `start_watch` / `stop_watch` / `refresh_watch` tools act on the current chat from tool context. **[done]**
- Watch routes registered on the automations router. **[done]**
- Integration (running stack): two scheduled runs on one chat — run 2 sees run 1 in checkpoint history.

## Deferred / out of scope

- Zero delivery-cost optimization (signal-column + REST fetch vs full-content sync) — app-wide, separate.
- Server-side turns surviving browser navigation for *interactive* chat ("zombie streaming").
- `start_watch` cadence UX refinements. Verbs/doors → `04`/`05`; agent playbook → `07`.
