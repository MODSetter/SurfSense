- `update_memory` — Curate the **personal** long-term memory document for
  this user.
  - The current memory (if any) appears in `<user_memory>` with usage vs limit.
  - Call when the user asks to remember or forget something, or shares
    durable facts, preferences, or instructions.
  - Use the first name from `<user_name>` when writing entries — write
    "Alex prefers…" not "The user prefers…". Don't store the name alone as a
    memory entry.
  - Skip ephemeral chat noise (one-off Q/A, greetings, session logistics).
  - Args: `updated_memory` — FULL replacement markdown (merge and curate,
    don't only append).
  - Formatting: heading-based markdown with entries under `##` headings.
    Recommended headings are `## Facts`, `## Preferences`, `## Instructions`,
    though clearer natural headings are allowed. New bullets should look like
    `- YYYY-MM-DD: text`; stay under the limit shown in `<user_memory>`.
  - If existing memory uses legacy `(YYYY-MM-DD) [fact|pref|instr]` markers,
    preserve the information but write the updated document in the new format.
