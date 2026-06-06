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
  - Formatting: heading-based markdown with entries under `##` headings.
    Recommended headings are `## Product Decisions`,
    `## Engineering Conventions`, `## Project Facts`, and `## Open Questions`.
    New bullets should look like `- YYYY-MM-DD: text`; stay under the limit
    shown in `<team_memory>`.
  - If existing memory uses legacy `(YYYY-MM-DD) [fact]` markers, preserve the
    information but write the updated document in the new format.
  - Do not create personal headings such as `## Preferences`,
    `## Instructions`, `## Personal Notes`, or `## Personal Instructions`.
    When trimming, prioritise: decisions/conventions > key facts > current
    priorities.
