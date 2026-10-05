export type WorkspaceEvent =
  | { type: "connected" }
  | {
      type: "documents" | "artifacts" | "chat-runs"
      ids: number[]
      status: string
    }

const CHANGED = ["documents", "artifacts", "chat-runs"] as const

/** One frame. A heartbeat, or a kind this client does not know, is nothing. */
function parseFrame(frame: string): WorkspaceEvent | null {
  if (frame.startsWith(": connected")) return { type: "connected" }
  const lines = frame.split(/\r?\n/)
  const field = (name: string) =>
    lines
      .find((line) => line.startsWith(`${name}:`))
      ?.slice(name.length + 1)
      .trimStart()
  const kind = CHANGED.find((known) => known === field("event"))
  const data = field("data")
  if (!kind || !data) return null
  return {
    type: kind,
    ...(JSON.parse(data) as { ids: number[]; status: string }),
  }
}

/** Reads a workspace's event stream, one event per frame, however the bytes are chunked. */
export async function* parseWorkspaceEvents(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<WorkspaceEvent> {
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
