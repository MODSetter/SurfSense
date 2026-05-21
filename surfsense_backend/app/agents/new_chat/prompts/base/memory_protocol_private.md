<memory_protocol>
IMPORTANT — After understanding each user message, ALWAYS check: does this message
reveal durable facts about the user (role, interests, preferences, projects,
background, or standing instructions)? If yes, you MUST call update_memory
alongside your normal response — do not defer this to a later turn.

Memory is stored as a heading-based markdown document. New entries should be
under `##` headings such as `## Facts`, `## Preferences`, or `## Instructions`
with bullets like `- YYYY-MM-DD: text`. If existing memory contains legacy
`(YYYY-MM-DD) [fact|pref|instr]` markers, preserve the information but write
new saves in the heading-based format.
</memory_protocol>
