import { ApiError } from "@/lib/api"

// What the chat model's check also reports, so the composer says it, not a reply.
const CLAUDE_CODE_REFUSALS = new Set([
  "claude_too_old",
  "claude_sign_in_required",
])

/** A send refused before it ran because the user's Claude Code cannot answer. */
export function isClaudeCodeRefusal(cause: unknown): boolean {
  return (
    cause instanceof ApiError &&
    cause.status === 409 &&
    cause.code !== null &&
    CLAUDE_CODE_REFUSALS.has(cause.code)
  )
}
