import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"

import { TooltipProvider } from "@/components/ui/tooltip"

import { SourcesPanel } from "./sources-panel"
import { useSources } from "./use-sources"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const LIST = "document_type=FILE&document_type=NOTE&limit=200&offset=0"

function source(id: number, title: string) {
  return {
    id,
    title,
    document_type: "NOTE" as const,
    status: "ready" as const,
    error_message: null,
    created_at: "2026-09-30T00:00:00Z",
    updated_at: "2026-09-30T00:00:00Z",
  }
}

function SourceHarness({ workspaceId = 1 }: { workspaceId?: number }) {
  const sources = useSources(workspaceId)
  return (
    <TooltipProvider>
      <SourcesPanel
        documents={sources.documents}
        selectedDocumentIds={sources.includedDocumentIds}
        highlightedDocumentId={null}
        isLoading={sources.isLoading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={vi.fn()}
        onToggleAll={vi.fn()}
      />
    </TooltipProvider>
  )
}

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
    documentsChanged: (ids: number[]) =>
      feed.enqueue(
        encoder.encode(
          `event: documents\ndata: ${JSON.stringify({ ids, status: "pending" })}\n\n`
        )
      ),
    drop: () => feed.close(),
  }
}

/** An API whose list grows by one source each time it is asked again. */
function apiListing(lists: ReturnType<typeof source>[][], streams: Response[]) {
  let listed = 0
  let opened = 0
  return vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith("/events")) {
      return streams[opened++] ?? new Promise<Response>(() => {})
    }
    if (path.endsWith(`/documents?${LIST}`)) {
      return Response.json(lists[Math.min(listed++, lists.length - 1)])
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("sources stay fresh", () => {
  it("shows a source another program added, when the workspace reports it", async () => {
    const stream = eventStream()
    vi.stubGlobal(
      "fetch",
      apiListing(
        [
          [source(1, "old.txt")],
          [source(2, "Word count #1"), source(1, "old.txt")],
        ],
        [stream.response]
      )
    )

    render(<SourceHarness />)
    await screen.findByText("old.txt")
    stream.connected()
    stream.documentsChanged([2])

    expect(await screen.findByText("Word count #1")).toBeTruthy()
  })

  it("reloads what it missed once a dropped stream is back", async () => {
    const first = eventStream()
    const second = eventStream()
    vi.stubGlobal(
      "fetch",
      apiListing(
        [
          [source(1, "old.txt")],
          [source(2, "Word count #1"), source(1, "old.txt")],
        ],
        [first.response, second.response]
      )
    )

    render(<SourceHarness />)
    await screen.findByText("old.txt")
    first.connected()
    first.drop()
    // The change itself happened while nothing was listening.
    second.connected()

    expect(
      await screen.findByText("Word count #1", {}, { timeout: 4000 })
    ).toBeTruthy()
  })

  it("stops listening to a workspace it left", async () => {
    const fetchMock = apiListing([[source(1, "old.txt")]], [])
    vi.stubGlobal("fetch", fetchMock)

    const { rerender } = render(<SourceHarness workspaceId={1} />)
    await screen.findByText("old.txt")
    rerender(<SourceHarness workspaceId={2} />)

    const opened = (path: string) =>
      fetchMock.mock.calls.find(([input]) => String(input) === path)
    await waitFor(() => expect(opened("/workspaces/2/events")).toBeTruthy())
    const [, left] = opened("/workspaces/1/events") as unknown as [
      string,
      RequestInit,
    ]
    expect(left.signal?.aborted).toBe(true)
  })

  it("still lists sources when the stream cannot open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith("/events")
          ? Response.json({ detail: "unavailable" }, { status: 503 })
          : Response.json([source(1, "old.txt")])
      )
    )

    render(<SourceHarness />)

    expect(await screen.findByText("old.txt")).toBeTruthy()
    expect(screen.queryByText("Source action failed")).toBeNull()
  })
})
