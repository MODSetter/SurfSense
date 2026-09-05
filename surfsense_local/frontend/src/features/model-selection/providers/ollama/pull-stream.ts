export type PullProgress = {
  status: string
  completed: number
  total: number
}

export async function* parsePullStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<PullProgress> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ""
      for (const line of lines) {
        if (line.trim()) {
          yield JSON.parse(line) as PullProgress
        }
      }

      if (done) {
        if (buffer.trim()) {
          yield JSON.parse(buffer) as PullProgress
        }
        return
      }
    }
  } finally {
    reader.releaseLock()
  }
}
