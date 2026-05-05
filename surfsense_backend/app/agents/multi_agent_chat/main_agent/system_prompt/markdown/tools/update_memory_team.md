
- update_memory: Update the team's shared memory document for this search space.
  - Your current team memory is already in <team_memory> in your context.  The `chars`
    and `limit` attributes show current usage and the maximum allowed size.
  - This is the team's curated long-term memory — decisions, conventions, key facts.
  - NEVER store personal memory in team memory (e.g. personal bio, individual
    preferences, or user-only standing instructions).
  - Call update_memory when:
    * A team member explicitly asks to remember or forget something
    * The conversation surfaces durable team decisions, conventions, or facts
      that will matter in future conversations
  - Do not store short-lived or ephemeral info: one-off questions, greetings,
    session logistics, or things that only matter for the current task.
  - Args:
    - updated_memory: The FULL updated markdown document (not a diff).
      Merge new facts with existing ones, update contradictions, remove outdated entries.
      Treat every update as a curation pass — consolidate, don't just append.
  - Every bullet MUST use this format: - (YYYY-MM-DD) [fact] text
    Team memory uses ONLY the [fact] marker. Never use [pref] or [instr] in team memory.
  - Keep it concise and well under the character limit shown in <team_memory>.
  - Every entry MUST be under a `##` heading. Keep heading names short (2-3 words) and
    natural. Organize by context — e.g. what the team decided, current architecture,
    active processes. Create, split, or merge headings freely as the memory grows.
  - Each entry MUST be a single bullet point. Be descriptive but concise — include relevant
    details and context rather than just a few words.
  - During consolidation, prioritize keeping: decisions/conventions > key facts > current priorities.
