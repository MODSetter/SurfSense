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
  - Formatting: bullets `- (YYYY-MM-DD) [marker] text` with markers `[fact]`,
    `[pref]`, `[instr]` (priority when trimming: `instr > pref > fact`).
    Group bullets under short `##` headings; stay under the limit shown in
    `<user_memory>`.
