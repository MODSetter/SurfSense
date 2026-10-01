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
})
