export type Citation = {
  chunk_id: number
  document_id: number
  start_line: number | null
  end_line: number | null
}

export type ChatStreamEvent =
  | { type: "delta"; text: string }
  | { type: "citations"; items: Citation[] }
  | { type: "error"; message: string }
  | { type: "done" }

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
