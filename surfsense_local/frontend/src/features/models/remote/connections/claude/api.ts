import { askEgress } from "@/features/egress/ask-egress"
import { allowAll } from "@/features/egress/api"
import { requestJson } from "@/lib/api"

import type { ModelType } from "../../../model-type"
import type { Connection } from "../api"

/** What SurfSense found of Claude Code on this computer, read live. */
export type ClaudeState = "not_installed" | "too_old" | "signed_out" | "ready"

type RefusedHost = { destination: string; host: string }

/** Whether a slot offers a Claude plan: answered at once, without running Claude Code. */
export type ClaudeOption = {
  serves: ModelType[]
  /** The hosts a Claude plan reaches that are still off, model calls first. */
  hosts: RefusedHost[]
}

export type ClaudeStatus = {
  state: ClaudeState
  version: string | null
  email: string | null
  /** As Claude Code reports it: `pro`, `max`, `team`. */
  plan: string | null
}

/** Anthropic's own install guide, the one outside page the dialog opens. */
export const CLAUDE_INSTALL_URL = "https://code.claude.com/docs/en/setup"

export const claudeOptionQueryKey = ["claude-plan-option"] as const

export function getClaudeOption(signal?: AbortSignal): Promise<ClaudeOption> {
  return requestJson<ClaudeOption>("/llm/connections/claude", { signal })
}

export const claudeStatusQueryKey = ["claude-plan-status"] as const

/** Runs the user's Claude Code, so only the dialog asks. */
export function getClaudeStatus(signal?: AbortSignal): Promise<ClaudeStatus> {
  return requestJson<ClaudeStatus>("/llm/connections/claude/status", { signal })
}

/** Nothing was made: the user kept a host the plan needs switched off. */
export class ClaudeHostDeclinedError extends Error {
  readonly host: string

  constructor(host: string) {
    super(host)
    this.name = "ClaudeHostDeclinedError"
    this.host = host
  }
}

/**
 * The Claude plan connection, once every host it reaches is allowed: asked
 * up front, in one question, so a refusal never stops it half made.
 */
export async function connectClaude(label: string): Promise<Connection> {
  const { hosts } = await getClaudeOption()
  const [first, ...rest] = hosts
  if (first) {
    const also = rest.map(({ host }) => host)
    const allowed = await askEgress({
      destination: first.destination,
      host: first.host,
      purpose: "claude_plan",
      also,
      allow: () => allowAll(first.destination, also),
    })
    if (!allowed) throw new ClaudeHostDeclinedError(first.host)
  }
  return requestJson<Connection>("/llm/connections/claude", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  })
}
