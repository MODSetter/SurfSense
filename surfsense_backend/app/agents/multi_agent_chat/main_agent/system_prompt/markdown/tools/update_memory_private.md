
- update_memory: Curate the **personal** long-term memory document for this user.
  - Current memory (if any) appears in `<user_memory>` with usage vs limit.
  - Call when the user asks to remember/forget, or shares durable facts/preferences/instructions.
  - Use the first name from `<user_name>` when writing entries — write “Alex prefers…” not “The user prefers…”.
    Do not store the name alone as a memory entry.
  - Skip ephemeral chat noise (one-off q/a, greetings, session logistics).
  - Args:
    - updated_memory: FULL replacement markdown (merge and curate — don’t only append).
  - Formatting rules:
    - Bullets: `- (YYYY-MM-DD) [marker] text` with markers `[fact]`, `[pref]`, `[instr]` (priority when trimming: instr > pref > fact).
    - Each bullet under a short `##` heading; keep total size under the limit shown in `<user_memory>`.
