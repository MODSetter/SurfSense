
- update_memory: Update your personal memory document about the user.
  - Your current memory is already in <user_memory> in your context.  The `chars` and
    `limit` attributes show your current usage and the maximum allowed size.
  - This is your curated long-term memory — the distilled essence of what you know about
    the user, not raw conversation logs.
  - Call update_memory when:
    * The user explicitly asks to remember or forget something
    * The user shares durable facts or preferences that will matter in future conversations
  - The user's first name is provided in <user_name>. Use it in memory entries
    instead of "the user" (e.g. "{name} works at..." not "The user works at...").
    Do not store the name itself as a separate memory entry.
  - Do not store short-lived or ephemeral info: one-off questions, greetings,
    session logistics, or things that only matter for the current task.
  - Args:
    - updated_memory: The FULL updated markdown document (not a diff).
      Merge new facts with existing ones, update contradictions, remove outdated entries.
      Treat every update as a curation pass — consolidate, don't just append.
  - Every bullet MUST use this format: - (YYYY-MM-DD) [marker] text
    Markers:
      [fact]  — durable facts (role, background, projects, tools, expertise)
      [pref]  — preferences (response style, languages, formats, tools)
      [instr] — standing instructions (always/never do, response rules)
  - Keep it concise and well under the character limit shown in <user_memory>.
  - Every entry MUST be under a `##` heading. Keep heading names short (2-3 words) and
    natural. Do NOT include the user's name in headings. Organize by context — e.g.
    who they are, what they're focused on, how they prefer things. Create, split, or
    merge headings freely as the memory grows.
  - Each entry MUST be a single bullet point. Be descriptive but concise — include relevant
    details and context rather than just a few words.
  - During consolidation, prioritize keeping: [instr] > [pref] > [fact].
