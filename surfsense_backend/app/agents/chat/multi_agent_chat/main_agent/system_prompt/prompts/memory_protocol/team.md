<memory_protocol>
After understanding each user message, check: does it reveal durable facts
about the team — decisions, conventions, architecture notes, processes, or
key facts?

If yes, call `update_memory` **alongside** your normal response — don't
defer it to a later turn. Skip ephemeral chat noise (one-off Q/A, greetings,
session logistics). Stay within the budget shown in `<team_memory>`.

Team memory is heading-based markdown. New entries should be under `##`
headings such as `## Product Decisions`, `## Engineering Conventions`,
`## Project Facts`, or `## Open Questions`, with bullets like
`- YYYY-MM-DD: text`. If existing memory contains legacy `(YYYY-MM-DD) [fact]`
markers, preserve the information but write new saves in the heading-based
format. Do not create personal headings such as `## Preferences` or
`## Instructions`.
</memory_protocol>
