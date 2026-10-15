import { ApiError } from "@/lib/api"

// Mirrors the refusal in modules/agent/agent_threads/turn.py.
const REFUSAL =
  "The selected model cannot run the agent. Choose another model, or start a new chat to use this one."

/** Whether the backend refused an agent thread's turn because the selected
 *  model cannot run the agent: the thread keeps its engine, so only a new
 *  chat takes that model. */
export function isUnsupportedModelRefusal(cause: unknown): boolean {
  return (
    cause instanceof ApiError &&
    cause.status === 409 &&
    cause.message === REFUSAL
  )
}
