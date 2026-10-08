import { afterEach, describe, expect, it, vi } from "vitest"

import { parseNumberedSseStream, type ChatStreamEvent } from "../sse"
import type { LivePair } from "./apply-frame"
import {
  beginRun,
  dropRun,
  liveRun,
  onRunEnded,
  onRunFrame,
  pump,
  runSummaries,
  subscribeToRuns,
  TEXT_NOTICE_GAP_MS,
  updatePair,
} from "./run-store"

const THREAD = 7

function pair(): LivePair {
  return [
    {
      id: 11,
      role: "user",
      content: { text: "How did revenue move?" },
      created_at: null,
      completed_at: null,
    },
    {
      id: 12,
      role: "assistant",
      content: { text: "", citations: [] },
      created_at: null,
      completed_at: null,
    },
  ]
}

/** A run's stream, written to a network read at a time. */
function followed() {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  let seq = 0
  const stream = new ReadableStream<Uint8Array>({
    start: (opened) => {
      controller = opened
    },
  })
  beginRun(THREAD, { workspaceId: 1, pair: pair() })
  const pumping = pump(THREAD, parseNumberedSseStream(stream))
  return {
    pumping,
    read(events: ChatStreamEvent[]) {
      const chunk = events
        .map((event) => `id: ${++seq}\ndata: ${JSON.stringify(event)}\n\n`)
        .join("")
      controller.enqueue(new TextEncoder().encode(chunk))
    },
    close() {
      controller.close()
      return pumping
    },
  }
}

const deltas = (count: number): ChatStreamEvent[] =>
  Array.from({ length: count }, (_, index) => ({
    type: "delta",
    text: `${index} `,
  }))

// Past the notice a read schedules: a macrotask after it, and no sooner than
// the gap after the last notice.
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const afterNotice = () => wait(TEXT_NOTICE_GAP_MS + 10)

const subscriptions: Array<() => void> = []
function subscriber() {
  const notices = vi.fn()
  subscriptions.push(subscribeToRuns(notices))
  return notices
}

afterEach(() => {
  for (const unsubscribe of subscriptions.splice(0)) unsubscribe()
})

describe("run store", () => {
  it("tells reads that come close together at most once a gap, and the last text always", async () => {
    const run = followed()
    await afterNotice()
    const notices = subscriber()

    // Ten reads a macrotask apart, each told on its own before the gap.
    const start = performance.now()
    for (let read = 0; read < 10; read++) {
      run.read(deltas(1))
      await wait(0)
    }
    const spent = performance.now() - start
    await afterNotice()

    expect(notices.mock.calls.length).toBeLessThan(10)
    expect(notices.mock.calls.length).toBeLessThanOrEqual(
      Math.ceil(spent / TEXT_NOTICE_GAP_MS) + 1
    )
    expect(liveRun(THREAD)?.pair?.[1].content.text).toBe("0 ".repeat(10))
    await run.close()
  })

  it("tells a read that follows a quiet spell without waiting", async () => {
    const run = followed()
    await afterNotice()
    const notices = subscriber()

    run.read(deltas(1))
    await wait(5)

    expect(notices).toHaveBeenCalledTimes(1)
    await run.close()
  })

  it("tells subscribers once of the frames one network read brings", async () => {
    const run = followed()
    const notices = subscriber()

    run.read(deltas(300))
    await afterNotice()

    expect(notices).toHaveBeenCalledTimes(1)
    expect(liveRun(THREAD)?.pair?.[1].content.text).toBe(
      deltas(300)
        .map((event) => (event.type === "delta" ? event.text : ""))
        .join("")
    )
    await run.close()
  })

  it("still hands each frame to its frame listeners", async () => {
    const run = followed()
    const heard = vi.fn()
    subscriptions.push(onRunFrame(heard))

    run.read(deltas(30))
    await run.close()

    expect(heard).toHaveBeenCalledTimes(30)
  })

  it("tells of its end at once, with the whole reply, before it is announced", async () => {
    const run = followed()
    const notices = subscriber()
    const ended = vi.fn(() => ({
      notices: notices.mock.calls.length,
      run: liveRun(THREAD),
    }))
    subscriptions.push(onRunEnded(ended))

    run.read([...deltas(3), { type: "delta", text: "done." }])
    await run.close()

    expect(ended).toHaveBeenCalledWith(THREAD)
    const seen = ended.mock.results[0]?.value
    expect(seen.notices).toBe(1)
    expect(seen.run?.ended).toBe(true)
    expect(seen.run?.pair?.[1].content.text).toBe("0 1 2 done.")
  })

  it("shows a stop the moment it is made", async () => {
    const run = followed()
    const notices = subscriber()

    updatePair(THREAD, ([user, assistant]) => [
      user,
      {
        ...assistant,
        content: { ...assistant.content, ending: { type: "stopped" } },
      },
    ])

    expect(notices).toHaveBeenCalledTimes(1)
    expect(liveRun(THREAD)?.pair?.[1].content.ending).toEqual({
      type: "stopped",
    })
    await run.close()
  })

  it("tells no one of a frame that changes nothing the run shows", async () => {
    const run = followed()
    const notices = subscriber()
    const heard = vi.fn()
    subscriptions.push(onRunFrame(heard))

    run.read([{ type: "thread-title-update", title: "Revenue" }])
    await afterNotice()

    expect(heard).toHaveBeenCalledTimes(1)
    expect(notices).not.toHaveBeenCalled()
    await run.close()
  })

  it("keeps its summary while text arrives, and changes it when the run does", async () => {
    const run = followed()
    const started = runSummaries()
    expect(started[THREAD]).toEqual({
      state: { state: "running" },
      ended: false,
      hasPair: true,
    })

    run.read(deltas(10))
    await afterNotice()
    expect(runSummaries()).toBe(started)

    run.read([{ type: "run-state", state: "queued", position: 2 }])
    await afterNotice()
    const queued = runSummaries()
    expect(queued[THREAD]?.state).toEqual({ state: "queued", position: 2 })

    run.read([{ type: "run-state", state: "queued", position: 2 }])
    await afterNotice()
    expect(runSummaries()).toBe(queued)

    await run.close()
    expect(runSummaries()[THREAD]?.ended).toBe(true)

    dropRun(THREAD)
    expect(runSummaries()[THREAD]).toBeUndefined()
  })
})
