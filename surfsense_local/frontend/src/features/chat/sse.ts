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
  // An agent turn's first frame: how many sources its folder is being given.
  | { type: "agent-preparing"; count: number }
  // The sources an agent turn works from, as the server resolved its ticks.
  | { type: "agent-scope"; scope: TurnSources }
  | ({ type: "agent-step" } & AgentStep)
  | ({ type: "permission-request" } & PermissionRequest)
  | { type: "permission-replied"; id: string; reply: string }
  // Where a run stands: waiting in line for the local runtime, or answering.
  | { type: "run-state"; state: "queued"; position: number }
  | { type: "run-state"; state: "running" }
  | { type: "done" }

/** A frame with the number the run gave it, for resuming where a window left off. */
export type NumberedEvent = { seq: number | null; event: ChatStreamEvent }

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
  | "runtime_busy"
  | "network"
  | "timeout"
  | "unknown"

function parseFrame(frame: string): NumberedEvent | null {
  const lines = frame.split(/\r?\n/)
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")

  if (!data) {
    return null
  }
  const id = lines.find((line) => line.startsWith("id:"))
  const seq = id ? Number(id.slice(3).trim()) : null
  const event: ChatStreamEvent =
    data === "[DONE]" ? { type: "done" } : (JSON.parse(data) as ChatStreamEvent)
  return { seq: Number.isFinite(seq) ? seq : null, event }
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<ChatStreamEvent> {
  for await (const numbered of parseNumberedSseStream(stream)) {
    yield numbered.event
  }
}

/** The stream's frames with their numbers, however the bytes are chunked. */
export async function* parseNumberedSseStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<NumberedEvent> {
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
