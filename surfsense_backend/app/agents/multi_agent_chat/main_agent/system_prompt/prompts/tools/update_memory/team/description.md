- `update_memory` — Curate the team's **shared** long-term memory document
  for this search space.
  - The current memory (if any) appears in `<team_memory>` with usage vs limit.
  - Call when a team member asks to remember or forget something, or when
    the conversation surfaces durable team decisions, conventions,
    architecture notes, processes, or key facts.
  - NEVER store personal memory in team memory (individual bios, personal
    preferences, user-only standing instructions).
  - Skip ephemeral chat noise (one-off Q/A, greetings, session logistics).
  - Args: `updated_memory` — FULL replacement markdown (merge and curate,
    don't only append).
  - Formatting: bullets `- (YYYY-MM-DD) [fact] text`. Team memory uses ONLY
    the `[fact]` marker (never `[pref]` or `[instr]`). Group bullets under
    short `##` headings (2-3 words each); stay under the limit shown in
    `<team_memory>`. When trimming, prioritise: decisions/conventions > key
    facts > current priorities.
