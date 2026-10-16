# Switching engines inside a thread

> An agent thread keeps working after a model change today because opencode holds its session for every model ([agent](../../architecture/agent.md#a-turn)). A Claude plan model runs on Claude Code, which holds a session of its own. When the selected model moves a thread from one engine to the other, the engine taking over is given a handover note: the thread's history since that engine last saw it, written as text and sent beside the user's message. The user switches models as freely as before.

Part of [Use your Claude plan](README.md). [T3 Code](https://github.com/pingdotgg/t3code/blob/main/docs/orchestration-v2/provider-switching-and-context.md) and [OpenClaw](https://docs.openclaw.ai/gateway/cli-backends) solve the same problem the same way: resume the engine's own session, and tell it what happened while it was away.

## The problem

An agent thread has two memories. The screen shows the user's messages and the replies. The engine also remembers every tool it called, what came back, and what it read. That second memory lives in the engine's session: opencode's database, or Claude Code's transcript. A model on the other engine starts with neither, though the screen still shows everything.

## Rejected: one engine per thread

A thread could keep the engine it started with and refuse a model on the other one with "start a new thread", as [Zed](https://zed.dev/docs/ai/agent-panel) does for its external agents. It is simpler, but a Claude plan model would be the only model a user cannot switch to mid-thread, and a plan running out mid-task would strand the thread.

## The session the new engine runs in

Before the first turn on an engine, `engines/handover.py` picks one of three, in this order:

| Case | Session | Note covers |
|---|---|---|
| The engine has never run this thread | new | every turn so far |
| The engine ran it before, and its session is fit to resume | the engine's own, resumed | only the turns since it was left |
| The engine ran it before, and its session is not fit | new | every turn so far |

A session is **not fit** when:

- **resuming fails**: opencode no longer has it, or Claude Code answers "No conversation found";
- **the account changed**: the Claude Code account `claude auth status` reports now is not the one the session was made under, which is stored with `claude_session_id`. OpenClaw "drops stored CLI session reuse when the selected auth identity changes" for the same reason. Not built: it needs the account stored beside the session, a column no other part needs, and SurfSense's copy of the session resumes under any account;
- **it is stale**: the thread has left that engine three times or more since its session last ran a turn, so its own memory is mostly notes. Not built: the note already covers every turn since the engine last answered.

## The note

Built from the engine being left: opencode's session read as the listing reads it, or SurfSense's mirrored Claude entries ([`03-agent.md`](03-agent.md#sessions)). It holds, oldest first:

1. Each user message, as the user wrote it, without the scope note.
2. Each reply's text.
3. Each tool call on one line: its name as the step shows it, its input, and its output cut to 2,000 characters.
4. The files under the thread's `outputs/` now, which both engines share since both work in the same folder.

Left out:

- **Reasoning.** Neither engine's thinking is passed on.
- **Stale output.** A tool output that showed a file's contents is dropped when a later call rewrote that file; the note names the file, and the current version is on disk.

**Too long.** The note is fitted to the new model's window less room for the turn: the newest turns kept whole, older tool outputs dropped first, then older replies cut to their first paragraph, then the oldest turns summarised in one line each.

## Where the note goes

Beside the user's message, never in a system prompt: opencode's is one configuration for every thread, and a resumed Claude Code session keeps the one it started with.

- **opencode**: a second text part marked `synthetic` on `prompt_async`, the way the scope note travels ([agent](../../architecture/agent.md#the-ticked-sources)).
- **Claude Code**: a separate text block before the user's text in the same user message.

Both start with the tag `<surfsense-handover>`, so reading the thread back strips them from the user's text, as the scope note is stripped.

Measured: Claude Code given a note of an opencode thread answered "Revenue grew 12% in Q3. The file saved was outputs/q3.md" without calling a tool. A resumed Claude Code session given a note as a separate block knew both what it had been told itself and what the note said, and its transcript kept the note as its own block. A Claude Code session read back gave every user and assistant message in order.

## Keeping the note

Each note is kept in the session of the engine it was for, as a block of the user message it went with, so it needs no table: reading the thread back leaves it out of the user's words, as it leaves out the scope note, and support reads it in that session. A later note never edits an earlier one. The note is fitted to 24,000 characters, about 6,000 tokens, which leaves room for the turn in the smallest window the agent runs in.

## Rejected: a history tool

A `surfsense_thread_history` tool that returns earlier turns and full tool results on request, as OpenClaw's `sessions_history` does, is not built. What a note leaves out can already be had again: files from `outputs/`, a source by searching or reading it, a plugin's result by calling it. What cannot is a cut plugin result whose data changed, took minutes, or had side effects. If that shows up in use, the full output of each cut tool call is written to `handover/<call id>.txt` in the thread's folder and the note names the file: both engines already read the folder, so no new tool, scope rule or permission is needed.

## What changes for the user

Nothing to do. The first message after a switch takes a little longer and uses a little more of the plan, because the note is sent with it. The new engine knows a tool was called and roughly what it returned, not every byte; it may call it again.

## The thread record

`agent_engine` names the engine the thread runs on now. `opencode_session_id` and `claude_session_id` stay set once made. Reading the thread merges both sessions' turns by time ([`both_sessions.py`](../../../surfsense_local/backend/modules/agent/engines/both_sessions.py)), so the screen shows one thread, and a step's whole result is found in whichever session holds it.
