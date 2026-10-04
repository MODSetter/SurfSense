import { afterEach, describe, expect, it, vi } from "vitest"

import { subscribeToWorkspaceChanges } from "./workspace-changes"

/** The workspace's event stream, fed by the test as the API would feed it. */
function eventStream() {
  let feed!: ReadableStreamDefaultController<Uint8Array>
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      feed = controller
    },
  })
  const encoder = new TextEncoder()
  return {
    response: new Response(body, {
      headers: { "Content-Type": "text/event-stream" },
    }),
    connected: () => feed.enqueue(encoder.encode(": connected\n\n")),
    changed: (kind: "documents" | "artifacts") =>
      feed.enqueue(
        encoder.encode(
          `event: ${kind}\ndata: ${JSON.stringify({ ids: [1], status: "ready" })}\n\n`
        )
      ),
    drop: () => feed.close(),
  }
}

function apiStreaming(streams: Response[]) {
  let opened = 0
  const fetchMock = vi.fn<
    (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
  >(async () => streams[opened++] ?? new Promise<Response>(() => {}))
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

const unsubscribes: (() => void)[] = []

function listen(workspaceId: number, kind: "documents" | "artifacts") {
  const listener = vi.fn()
  unsubscribes.push(subscribeToWorkspaceChanges(workspaceId, kind, listener))
  return listener
}

afterEach(() => {
  for (const unsubscribe of unsubscribes.splice(0)) unsubscribe()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe("workspace changes", () => {
  it("opens one stream for a workspace, however many lists listen", async () => {
    const stream = eventStream()
    const fetchMock = apiStreaming([stream.response])

    const documents = listen(1, "documents")
    const artifacts = listen(1, "artifacts")
    stream.connected()
    stream.changed("artifacts")

    await vi.waitFor(() => expect(artifacts).toHaveBeenCalledOnce())
    expect(documents).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(String(fetchMock.mock.calls[0][0])).toBe("/workspaces/1/events")
  })

  it("keeps the stream until its last listener leaves", async () => {
    const stream = eventStream()
    const fetchMock = apiStreaming([stream.response])

    listen(1, "documents")
    listen(1, "artifacts")
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    const signal = fetchMock.mock.calls[0][1]?.signal

    unsubscribes.shift()?.()
    expect(signal?.aborted).toBe(false)
    unsubscribes.shift()?.()
    expect(signal?.aborted).toBe(true)
  })

  it("tells every list once a dropped stream is back", async () => {
    const first = eventStream()
    const second = eventStream()
    apiStreaming([first.response, second.response])

    const documents = listen(1, "documents")
    const artifacts = listen(1, "artifacts")
    first.connected()
    first.drop()
    second.connected()

    await vi.waitFor(
      () => {
        expect(documents).toHaveBeenCalledOnce()
        expect(artifacts).toHaveBeenCalledOnce()
      },
      { timeout: 4000 }
    )
  })

  it("removes every abort listener wait() adds across dropped streams", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] })
    const first = eventStream()
    const second = eventStream()
    const third = eventStream()
    const fetchMock = apiStreaming([
      first.response,
      second.response,
      third.response,
    ])

    listen(1, "documents")
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const signal = fetchMock.mock.calls[0][1]?.signal as AbortSignal
    const addListenerSpy = vi.spyOn(signal, "addEventListener")
    const removeListenerSpy = vi.spyOn(signal, "removeEventListener")

    first.drop()
    await vi.advanceTimersByTimeAsync(1_000)
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    second.drop()
    await vi.advanceTimersByTimeAsync(2_000)
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))

    const abortAdds = addListenerSpy.mock.calls.filter(([event]) => event === "abort")
    const abortRemoves = removeListenerSpy.mock.calls.filter(
      ([event]) => event === "abort"
    )

    expect(abortAdds.length).toBeGreaterThanOrEqual(2)
    expect(abortRemoves.length).toBe(abortAdds.length)
  })

  it("tears the subscription down during a retry wait without waiting out the timer", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] })
    const stream = eventStream()
    const fetchMock = apiStreaming([stream.response])

    const unsubscribe = subscribeToWorkspaceChanges(1, "documents", vi.fn())
    unsubscribes.push(unsubscribe)
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const signal = fetchMock.mock.calls[0][1]?.signal as AbortSignal

    stream.drop()
    await vi.waitFor(() => expect(vi.getTimerCount()).toBe(1))

    unsubscribe()

    expect(signal.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(0)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
