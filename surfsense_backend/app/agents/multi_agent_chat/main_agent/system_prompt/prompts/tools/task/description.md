- `task` — Invoke a specialist subagent.
  - Specialists own workspace knowledge-base operations and connected
    third-party services (Slack, Notion, Jira, Gmail, etc.). See
    `<specialists>` for the live roster.
  - Each subagent runs in isolation with its own tool stack and context,
    and returns a single synthesized result.
  - Args:
    - `subagent_type` — name of the specialist to invoke (must match an
      entry in `<specialists>`).
    - `description` — the FULL task prompt. The specialist cannot see this
      thread, so include all context and constraints, plus what you need
      back. The specialist will respond in its own format — don't dictate
      one.
  - Rules:
    - One `task` call per turn. Bundle related work for the same specialist
      into one invocation; the parent graph cannot coordinate human
      approvals across parallel subagents.
    - Don't claim to already know what a specialist's source contains;
      invoke it and use what it returns.
