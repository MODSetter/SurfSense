import { describe, expect, it } from "vitest"

import { parseNumberedSseStream, parseSseStream } from "./sse"

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

  it("finds a blank line however the reads split it", async () => {
    const text =
      'id: 1\r\ndata: {"type":"delta","text":"a"}\r\n\r\n' +
      'id: 2\r\ndata: {"type":"delta","text":"b"}\n\n' +
      'id: 3\ndata: {"type":"delta","text":"c"}\r\n\r\ndata: [DONE]\r\n\r\n'
    const expected = [
      { seq: 1, event: { type: "delta", text: "a" } },
      { seq: 2, event: { type: "delta", text: "b" } },
      { seq: 3, event: { type: "delta", text: "c" } },
      { seq: null, event: { type: "done" } },
    ]

    for (let at = 1; at < text.length; at += 1) {
      const events = []
      const stream = chunkedStream([text.slice(0, at), text.slice(at)])
      for await (const event of parseNumberedSseStream(stream)) {
        events.push(event)
      }
      expect(events, `split at ${at}`).toEqual(expected)
    }
    const oneByOne = []
    for await (const event of parseNumberedSseStream(
      chunkedStream([...text])
    )) {
      oneByOne.push(event)
    }
    expect(oneByOne).toEqual(expected)
  })

  it("reads a large frame in small pieces in time that grows with its size", async () => {
    // An agent step's input is not capped: a written file arrives whole.
    const input = { content: "x".repeat(4_000_000) }
    const step = {
      type: "agent-step",
      id: "s",
      tool: "write",
      status: "completed",
      title: "Write",
      input,
    }
    const frame = `id: 1\r\ndata: ${JSON.stringify(step)}\r\n\r\n`
    const pieces = []
    for (let at = 0; at < frame.length; at += 1024) {
      pieces.push(frame.slice(at, at + 1024))
    }

    const started = performance.now()
    const events = []
    for await (const event of parseSseStream(chunkedStream(pieces))) {
      events.push(event)
    }

    // Searching the whole unfinished frame at each of its 3,900 reads took
    // about 4 s here; reading each piece once, about 40 ms.
    expect(performance.now() - started).toBeLessThan(1_000)
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: "agent-step", input })
  })
})
