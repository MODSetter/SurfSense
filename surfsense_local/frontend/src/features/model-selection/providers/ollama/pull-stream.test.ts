import { describe, expect, it } from "vitest"

import { parsePullStream } from "./pull-stream"

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

describe("parsePullStream", () => {
  it("parses progress objects split across arbitrary network chunks", async () => {
    const steps = []
    const stream = chunkedStream([
      '{"status":"pulling manifest","completed":0,"total":0}\n{"status":"dow',
      'nloading","completed":50,"total":100}\n',
      '{"status":"success","completed":100,"total":100}\n',
    ])

    for await (const step of parsePullStream(stream)) {
      steps.push(step)
    }

    expect(steps).toEqual([
      { status: "pulling manifest", completed: 0, total: 0 },
      { status: "downloading", completed: 50, total: 100 },
      { status: "success", completed: 100, total: 100 },
    ])
  })

  it("accepts a final line without a trailing newline", async () => {
    const steps = []
    for await (const step of parsePullStream(
      chunkedStream(['{"status":"success","completed":1,"total":1}'])
    )) {
      steps.push(step)
    }

    expect(steps).toEqual([{ status: "success", completed: 1, total: 1 }])
  })
})
