import type { ThreadMessageLike } from "@assistant-ui/react"

import type { AgentStep } from "@/features/agent/api"

import type { ChatMessage, MessageContent } from "./api"
import { attachmentsOf } from "./image-attachments"
import type { LivePair } from "./runs/apply-frame"
import type { Citation } from "./sse"
import type { ChatTurnError } from "./use-chat-runtime"

export const OPTIMISTIC_ID = "optimistic-"

/** A placeholder id, sent before `accepted` names the stored turn. */
export function isOptimistic(id: number | string) {
  return String(id).startsWith(OPTIMISTIC_ID)
}

/**
 * The thread as shown: its stored turns, with the reply a run is writing in
 * place of its stored copy. The question is the stored one once it exists,
 * which a reattached run never had the text of.
 */
export function composedThread(
  persisted: ChatMessage[],
  pair: LivePair | null,
  replaces: ReadonlyArray<number | string>
): ChatMessage[] {
  if (!pair) return persisted
  const [user, assistant] = pair
  const hidden = new Set([...replaces, user.id, assistant.id])
  const question = persisted.find((message) => message.id === user.id) ?? user
  return [
    ...persisted.filter((message) => !hidden.has(message.id)),
    question,
    assistant,
  ]
}

function errorOf(
  message: ChatMessage,
  latestAssistantId: string | null
): ChatTurnError | null {
  const ending = message.content.ending
  const retryable = String(message.id) === latestAssistantId
  if (ending?.type === "error") {
    return {
      kind: ending.kind,
      message: ending.message,
      provider: ending.provider ?? "",
      detailIsLocal: ending.local,
      retryable,
    }
  }
  if (ending?.type === "interrupted") {
    return { kind: "interrupted", message: "", provider: "", retryable }
  }
  return null
}

// Shared, so a reply without them selects the same value at every frame.
const NO_CITATIONS: Citation[] = []
const NO_STEPS: AgentStep[] = []

type ShownReasoning = { text: string; durationMs: number | null }

// One per trace the frames built: an answer token keeps the trace, so the
// header that draws it is not re-rendered for a token it does not show.
const shownReasonings = new WeakMap<
  NonNullable<MessageContent["reasoning"]>,
  ShownReasoning
>()

function shownReasoning(
  reasoning: MessageContent["reasoning"]
): ShownReasoning | null {
  if (!reasoning) return null
  let shown = shownReasonings.get(reasoning)
  if (!shown) {
    shown = { text: reasoning.text, durationMs: reasoning.duration_ms }
    shownReasonings.set(reasoning, shown)
  }
  return shown
}

export function toRuntimeMessage(
  message: ChatMessage,
  latestAssistantId: string | null,
  threadId: number | null
): ThreadMessageLike {
  const value =
    message.role === "assistant" ? message.completed_at : message.created_at
  // SQLite stores CURRENT_TIMESTAMP in UTC but returns it without an offset.
  const timestamp =
    value && !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? `${value}Z` : value
  const error =
    message.role === "assistant" ? errorOf(message, latestAssistantId) : null
  const stopped =
    message.role === "assistant" && message.content.ending?.type === "stopped"
  return {
    id: String(message.id),
    role: message.role,
    content: [{ type: "text", text: message.content.text ?? "" }],
    ...(message.role === "user"
      ? { attachments: attachmentsOf(message, threadId) }
      : {}),
    ...(timestamp ? { createdAt: new Date(timestamp) } : {}),
    ...(error
      ? { status: { type: "incomplete", reason: "error", error } as const }
      : stopped
        ? // Without it assistant-ui calls a stopped reply complete.
          { status: { type: "incomplete", reason: "cancelled" } as const }
        : {}),
    metadata: {
      custom: {
        citations: message.content.citations ?? NO_CITATIONS,
        steps: message.content.steps ?? NO_STEPS,
        reasoning: shownReasoning(message.content.reasoning),
        progress: message.content.progress ?? null,
        queue: message.content.queue ?? null,
        preparing: message.content.preparing ?? null,
        scope: message.content.scope ?? null,
      },
    },
  }
}
