# ADR 0090: A document waits on the server for the pictures it places

- **Status:** Accepted
- **Date:** 2026-11-10
- **Supersedes:** in part, [ADR 0087](0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md): "A document needing a picture still being drawn waits for the user's next message"
- **Source:** maintainer decision, 10 Nov 2026 (no permalink)

## Context

A local picture on a processor takes minutes, past a tool call's limit, so its call answers queued. A render naming it was refused, and the agent could only tell the user to ask again: a four-page comic drawn on this computer never became one PDF on its own. A tool that polls, or a turn kept open, would hold a call past its limit, which ADR 0087 rules out.

## Decision

- A render naming a picture still being drawn is made pending with the pictures it waits for, unqueued, and its call answers at once.
- The end of every Studio job queues the renders waiting on that picture once all of theirs are drawn, and fails one whose picture failed, was cancelled or deleted, with a sentence naming it. The worker does the same when it starts.
- Only a render waits. A web page still refuses a picture being drawn, since it is checked and screenshotted as it is saved.

## Consequences

- A comic drawn slowly ends as a PDF without the user asking again.
- No process, timer or model stays awake for it: the job that ends is the one event that can make the render ready.
- No one looks at a waiting render's pages, since it finishes after its turn; a comic's PDF is a fixed layout.
