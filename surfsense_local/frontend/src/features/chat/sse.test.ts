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
      'data: {"type":"accepted","user_message_id":11,"assistant_message_id":12,"user_created_at":"2026-09-08T00:00:00"}\n\ndata: {"type":"del',
      'ta","text":"hel"}\n\ndata: {"type":"thread-title-update","title":"Revenue Growth"}',
      '\n\ndata: {"type":"delta","text":"lo"}',
      '\n\ndata: {"type":"citation-catalog","items":[{"source_id":1,"chunk_id":4,"document_id":2,',
      '"start_line":10,"end_line":12}]}\n\ndata: {"type":"citations","items":[{"source_id":1,"chunk_id":4,"document_id":2,',
      '"start_line":10,"end_line":12}]}\n\ndata: {"type":"completed","assistant_completed_at":"2026-09-08T00:00:05"}\n\ndata: [DONE]\n\n',
    ])

    for await (const event of parseSseStream(stream)) {
      events.push(event)
    }

    expect(events).toEqual([
      {
        type: "accepted",
        user_message_id: 11,
        assistant_message_id: 12,
        user_created_at: "2026-09-08T00:00:00",
      },
      { type: "delta", text: "hel" },
      { type: "thread-title-update", title: "Revenue Growth" },
      { type: "delta", text: "lo" },
      {
        type: "citation-catalog",
        items: [
          {
            source_id: 1,
            chunk_id: 4,
            document_id: 2,
            start_line: 10,
            end_line: 12,
          },
        ],
      },
      {
        type: "citations",
        items: [
          {
            source_id: 1,
            chunk_id: 4,
            document_id: 2,
            start_line: 10,
            end_line: 12,
          },
        ],
      },
      {
        type: "completed",
        assistant_completed_at: "2026-09-08T00:00:05",
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
