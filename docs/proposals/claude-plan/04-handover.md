# Switching engines inside a thread

> An agent thread keeps working after a model change today because opencode holds its session for every model ([agent](../../architecture/agent.md#a-turn)). A Claude plan model runs on Claude Code, which holds a session of its own. When the selected model moves a thread from one engine to the other, the engine taking over is given a handover note: the thread's history written as text. The user switches models as freely as before.

Part of [Use your Claude plan](README.md).

## The problem

An agent thread has two memories. The screen shows the user's messages and the replies. The engine also remembers every tool it called, what came back, and what it read. That second memory lives in the engine's session: opencode's database, or Claude Code's transcript. A model on the other engine starts with neither, though the screen still shows everything.

## Rejected: one engine per thread

A thread could keep the engine it started with and refuse a model on the other one with "start a new thread". It is simpler, but a Claude plan model would be the only model a user cannot switch to mid-thread, and a plan running out mid-task would strand the thread.

## The note

Before the first turn on the new engine, `engines/handover.py` builds the note from the engine being left:

- **From opencode**: its session's messages, read as the listing reads them today.
- **From Claude Code**: SurfSense's mirrored entries ([`03-agent.md`](03-agent.md#sessions)), or `get_session_messages`.

The note holds, oldest first:

1. Each user message, as the user wrote it, without the scope note.
2. Each reply's text.
3. Each tool call: its name as the step shows it, its input, and its output cut to 2,000 characters, written as text, not as tool history.
4. The files under the thread's `outputs/`, which both engines share since both work in the same folder.

It goes into the new engine's system prompt, after SurfSense's own, inside `<handover>…</handover>` with one line saying the thread was started with another model. The user's message is sent as usual.

**Too long.** The note is fitted to the new model's window less room for the turn: the newest turns kept whole, older tool outputs dropped first, then older replies cut to their first paragraph, and the oldest turns, past that, summarised in one line each.

**Measured.** Claude Code given a note of an opencode thread answered "Revenue grew 12% in Q3. The file saved was outputs/q3.md" without calling a tool; a Claude Code session read back gave every user and assistant message in order.

## What changes for the user

Nothing to do. The first message after a switch takes a little longer and uses a little more of the plan, because the note is sent with it. The new engine knows a tool was called and roughly what it returned, not every byte; it may call it again.

## Switching back

Each engine keeps its own session. Switching back to an engine the thread used before resumes its session and adds a note of only the turns since it was left.

## The thread record

`agent_engine` names the engine the thread runs on now; `opencode_session_id` and `claude_session_id` stay set once made. `thread_messages` merges both sessions' turns by time, so the screen shows one thread.
