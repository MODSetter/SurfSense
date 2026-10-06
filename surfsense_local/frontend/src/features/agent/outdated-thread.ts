import { ApiError } from "@/lib/api"

// Mirrors LEGACY_TURN in modules/agent/agent_threads/legacy_thread.py.
const REFUSAL =
  "This agent chat was started before each chat kept its own sources. Start a new chat to continue."

/** Whether the backend refused a turn because the agent thread predates
 *  per-chat folders: it can be read back, never continued. */
export function isOutdatedThreadRefusal(cause: unknown): boolean {
  return (
    cause instanceof ApiError &&
    cause.status === 409 &&
    cause.message === REFUSAL
  )
}
