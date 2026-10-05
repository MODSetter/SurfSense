import type { AgentStep } from "@/features/agent/api"

import type { ChatMessage, MessageContent } from "../api"
import type { ChatStreamEvent } from "../sse"

/**
 * The question and the reply a run is writing: the user's turn, then the
 * assistant's. Placeholders until `accepted` names their stored ids.
 */
export type LivePair = [ChatMessage, ChatMessage]

/**
 * The pair after one frame. Pure, so a reply rebuilt from a replay is the reply
 * a window watched live. A reattached run starts with no pair at all: the
 * `accepted` frame makes one, and the question's text is the stored turn's.
 */
export function applyFrame(
  previous: LivePair | null,
  event: ChatStreamEvent
): LivePair | null {
  const pair = withoutPreparing(previous, event)
  if (event.type === "accepted") {
    if (pair === null) {
      return [
        turn(
          event.user_message_id,
          "user",
          { text: "" },
          event.user_created_at
        ),
        turn(event.assistant_message_id, "assistant", {
          text: "",
          citations: [],
        }),
      ]
    }
    const [user, assistant] = pair
    return [
      { ...user, id: event.user_message_id, created_at: event.user_created_at },
      { ...assistant, id: event.assistant_message_id },
    ]
  }
  if (pair === null) return null
  const reply = (change: (content: MessageContent) => Partial<ChatMessage>) => {
    const [user, assistant] = pair
    return [user, { ...assistant, ...change(assistant.content) }] as LivePair
  }
  const content = (change: (current: MessageContent) => MessageContent) =>
    reply((current) => ({ content: change(current) }))

  switch (event.type) {
    case "agent-preparing":
      return content((current) => ({ ...current, preparing: event.count }))
    case "agent-scope": {
      // The server's resolution replaces the panel's guess.
      const [user, assistant] = pair
      return [
        { ...user, content: { ...user.content, scope: event.scope } },
        assistant,
      ]
    }
    case "run-state":
      return content((current) =>
        event.state === "queued"
          ? { ...current, queue: { position: event.position } }
          : { ...current, queue: undefined }
      )
    case "completed":
      return reply((current) => ({
        completed_at: event.assistant_completed_at,
        content: {
          ...current,
          ...(event.text !== undefined ? { text: event.text } : {}),
        },
      }))
    case "citation-catalog":
    case "citations":
      return content((current) => ({ ...current, citations: event.items }))
    case "prompt-progress":
      return content((current) => ({
        ...current,
        progress: { processed: event.processed, total: event.total },
      }))
    case "reasoning":
      return content((current) => ({
        ...current,
        reasoning: {
          text: (current.reasoning?.text ?? "") + event.text,
          duration_ms: null,
        },
      }))
    case "reasoning-end":
      return content((current) =>
        current.reasoning
          ? {
              ...current,
              reasoning: {
                ...current.reasoning,
                duration_ms: event.duration_ms,
              },
            }
          : current
      )
    case "delta":
      return content((current) => ({
        ...current,
        text: (current.text ?? "") + event.text,
      }))
    case "agent-step":
      return content((current) => ({
        ...current,
        steps: withStep(current.steps, stepFrom(event)),
      }))
    case "error":
      return content((current) => ({
        ...current,
        ending: {
          type: "error",
          kind: event.kind,
          message: event.message,
          provider: event.provider,
        },
      }))
    default:
      return pair
  }
}

function turn(
  id: number | string,
  role: "user" | "assistant",
  content: MessageContent,
  createdAt: string | null = null
): ChatMessage {
  return { id, role, content, created_at: createdAt, completed_at: null }
}

/** The step an `agent-step` frame describes, without the frame's own type. */
function stepFrom(
  event: Extract<ChatStreamEvent, { type: "agent-step" }>
): AgentStep {
  const { id, tool, status, title, input, output, error, artifact } = event
  return { id, tool, status, title, input, output, error, artifact }
}

/** An agent turn's preparing line shows from its frame until any other arrives. */
function withoutPreparing(
  pair: LivePair | null,
  event: ChatStreamEvent
): LivePair | null {
  if (pair === null || event.type === "agent-preparing") return pair
  const [user, assistant] = pair
  if (assistant.content.preparing === undefined) return pair
  return [
    user,
    { ...assistant, content: { ...assistant.content, preparing: undefined } },
  ]
}

/** The reply's steps with this one added, or updated where it already is. */
function withStep(steps: AgentStep[] | undefined, step: AgentStep) {
  const current = steps ?? []
  return current.some((candidate) => candidate.id === step.id)
    ? current.map((candidate) => (candidate.id === step.id ? step : candidate))
    : [...current, step]
}
