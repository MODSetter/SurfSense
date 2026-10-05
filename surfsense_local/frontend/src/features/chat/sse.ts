import type {
  AgentStep,
  PermissionRequest,
  TurnSources,
} from "@/features/agent/api"

export type Citation = {
  source_id: number
  chunk_id: number
  document_id: number
  start_line: number | null
  end_line: number | null
  title?: string
}

export type ChatStreamEvent =
  | {
      type: "accepted"
      // An agent thread's ids are opencode's, which are strings.
      user_message_id: number | string
      assistant_message_id: number | string
      user_created_at: string
    }
  | { type: "thread-title-update"; title: string }
  | { type: "citation-catalog"; items: Citation[] }
  // Prompt tokens read so far out of those left to read; local runtime only.
  | { type: "prompt-progress"; processed: number; total: number }
  | { type: "reasoning"; text: string }
  | { type: "reasoning-end"; duration_ms: number }
  | { type: "delta"; text: string }
  | { type: "citations"; items: Citation[] }
  | { type: "completed"; assistant_completed_at: string; text?: string }
  | {
      type: "error"
      kind: ChatErrorKind
      message: string
      provider: string
    }
  // The sources an agent turn works from, as the server resolved its ticks.
  | { type: "agent-scope"; scope: TurnSources }
  | ({ type: "agent-step" } & AgentStep)
  | ({ type: "permission-request" } & PermissionRequest)
  | { type: "permission-replied"; id: string; reply: string }
  | { type: "done" }

// Mirrors modules/chat/errors.py's ChatErrorKind — keep the two in sync.
export type ChatErrorKind =
  | "provider_auth"
  | "provider_not_found"
  | "provider_rate_limited"
  | "provider_unavailable"
  | "model_cannot_run"
  | "context_too_long"
  | "subscription_sign_in"
  | "subscription_limit"
  | "network"
  | "timeout"
  | "unknown"

function parseFrame(frame: string): ChatStreamEvent | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")

  if (!data) {
    return null
  }
  if (data === "[DONE]") {
    return { type: "done" }
  }
  return JSON.parse(data) as ChatStreamEvent
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<ChatStreamEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ""
      for (const frame of frames) {
        const event = parseFrame(frame)
        if (event) {
          yield event
        }
      }

      if (done) {
        const event = parseFrame(buffer)
        if (event) {
          yield event
        }
        return
      }
    }
  } finally {
    reader.releaseLock()
  }
}
