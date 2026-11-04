# ADR 0079: `@` names sources and artifacts, not plugins

- **Status:** Accepted
- **Date:** 2026-11-04
- **Supersedes:** the part of [ADR 0069](0069-opencode-calls-tools-natively-and-holds-what-a-turn-needs.md) that holds a mentioned plugin whole, and the `@` mentions of [ADR 0065](0065-a-turns-plugin-tools-are-sized-by-the-window-not-counted.md)
- **Source:** maintainer decision, 4 Nov 2026 (no permalink)

## Context

Since ADR 0069 every ready plugin is in reach without a mention. A plugin mention added a note repeating the user's words, and past the tool share held the whole plugin rather than its 5 best tools, which a name in the message already holds; on Claude Code it added only the note. A source is different: a turn cannot read one outside its scope, and on every source nothing tells the agent which file was meant.

## Decision

- The `@` list holds sources, folders and artifacts. Plugins leave it, and the mention path through tool holding goes with them.
- A message sends what it named as ids, `mentioned_sources`, beside its text. The text is what the user reads; parsing it cannot tell two sources of one title apart, and it matched `me@notes.com` as a plugin.
- A named source joins the thread's scope for the rest of the thread, whatever is ticked, because a follow-up about it must not be refused. It is kept beside the ticks in `source_scope`'s JSON, so no migration, and each send's ticks replace only the ticks.
- A named folder is stored as its ready files at that moment: a folder in the scope would be taken back out by an excluded parent.
- `@` first offers Sources and Artifacts, and typing a name searches both. `/` stays free for commands, and one trigger means "point at something". A long list draws more as it scrolls; it is paged on the client, as the dashboard already holds every source and artifact.
- Agentic threads only. A Basic chat only filters retrieval by source, so with everything ticked, naming one would change nothing.

## Consequences

- Past the tool share, a tool outside a plugin's best 5 can take a step more to reach. Typing `@linear` by hand still counts as naming it.
- Nothing yet removes a named source from a thread but a new chat. The line under the message shows it.
- A file added to a named folder later is not in scope unless ticked.
- Naming something takes one more step unless a name is typed. Rows are not virtualized, so scrolling through thousands keeps them all on the page.
- The textarea shows a mention as plain text, not a chip.
