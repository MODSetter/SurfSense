/** Reads a newline-delimited JSON stream, one value per line, however the bytes are chunked. */
export async function* parseNdjson<T>(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<T> {
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
          yield JSON.parse(line) as T
        }
      }

      if (done) {
        if (buffer.trim()) {
          yield JSON.parse(buffer) as T
        }
        return
      }
    }
  } finally {
    reader.releaseLock()
  }
}
