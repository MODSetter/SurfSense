import { describe, expect, it } from "vitest"

import { parseSseStream } from "./sse"

function chunkedStream(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

describe("parseSseStream", () => {
  it("buffers frames split across arbitrary network chunks", async () => {
    const events = []
    const stream = chunkedStream([
      'data: {"type":"del',
      'ta","text":"hel"}\n\ndata: {"type":"delta","text":"lo"}',
      '\n\ndata: {"type":"citations","items":[{"chunk_id":4,"document_id":2,',
      '"start_line":10,"end_line":12}]}\n\ndata: [DONE]\n\n',
    ])

    for await (const event of parseSseStream(stream)) {
      events.push(event)
    }

    expect(events).toEqual([
      { type: "delta", text: "hel" },
      { type: "delta", text: "lo" },
      {
        type: "citations",
        items: [
          {
            chunk_id: 4,
            document_id: 2,
            start_line: 10,
            end_line: 12,
          },
        ],
      },
      { type: "done" },
    ])
  })

  it("accepts a final frame without a trailing blank line", async () => {
    const events = []
    for await (const event of parseSseStream(
      chunkedStream(['data: {"type":"error","message":"offline"}'])
    )) {
      events.push(event)
    }
    expect(events).toEqual([{ type: "error", message: "offline" }])
  })
})
