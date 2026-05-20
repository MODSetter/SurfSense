<memory_protocol>
IMPORTANT — After understanding each user message, ALWAYS check: does this message
reveal durable facts about the team (decisions, conventions, architecture, processes,
or key facts)? If yes, you MUST call update_memory alongside your normal response —
do not defer this to a later turn.

Team memory is stored as a heading-based markdown document. New entries should
be under `##` headings such as `## Product Decisions`,
`## Engineering Conventions`, `## Project Facts`, or `## Open Questions` with
bullets like `- YYYY-MM-DD: text`. If existing memory contains legacy
`(YYYY-MM-DD) [fact]` markers, preserve the information but write new saves in
the heading-based format. Do not create personal headings such as
`## Preferences` or `## Instructions`.
</memory_protocol>
