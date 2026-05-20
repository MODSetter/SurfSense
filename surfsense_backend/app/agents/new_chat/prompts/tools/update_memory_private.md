
- update_memory: Update your personal memory document about the user.
  - Your current memory is already in <user_memory> in your context. The `chars`
    and `limit` attributes show current usage and the maximum allowed size.
  - This is curated long-term memory, not raw conversation logs.
  - Call update_memory when the user explicitly asks to remember/forget
    something or shares durable facts, preferences, or standing instructions.
  - The user's first name is provided in <user_name>. Use it in entries instead
    of "the user" when helpful. Do not store the name alone as a memory entry.
  - Do not store short-lived info: one-off questions, greetings, session
    logistics, or things that only matter for the current task.
  - Args:
    - updated_memory: The FULL updated markdown document, not a diff. Merge new
      facts with existing ones, update contradictions, remove outdated entries,
      and consolidate instead of only appending.
  - Use heading-based Markdown:
    * Every entry must be under a `##` heading.
    * Recommended headings: `## Facts`, `## Preferences`, `## Instructions`.
      Specific natural headings are allowed when clearer.
    * New bullets should use `- YYYY-MM-DD: text`.
    * Each entry should be one concise but descriptive bullet.
  - If existing memory uses legacy `(YYYY-MM-DD) [fact|pref|instr]` markers,
    preserve the information but write the updated document in the new
    heading-based format.
  - During consolidation, prioritize durable instructions and preferences before
    generic facts.
