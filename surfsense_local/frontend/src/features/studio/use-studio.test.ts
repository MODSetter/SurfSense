import { afterEach, describe, expect, it, vi } from "vitest"
import { createElement, type ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import {
  cleanup,
  renderHook as renderBareHook,
  waitFor,
} from "@testing-library/react"
import { toast } from "sonner"

import { createQueryClient } from "@/lib/query-client"

import { useStudio } from "./use-studio"
import type { Artifact } from "./api"

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function artifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: 1,
    document_id: 1,
    format: "summary",
    generation: 1,
    title: "Summary of the source",
    status: "processing",
    error_message: null,
    created_at: "2026-09-15T00:00:00Z",
    updated_at: "2026-09-15T00:00:00Z",
    ...overrides,
  }
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
    artifactsChanged: (ids: number[]) =>
      feed.enqueue(
        encoder.encode(
          `event: artifacts\ndata: ${JSON.stringify({ ids, status: "ready" })}\n\n`
        )
      ),
  }
}

/** An API that answers each new read of the artifact list with the next one. */
function studioApi(lists: Artifact[][]) {
  const stream = eventStream()
  let listed = 0
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith("/events")) return stream.response
    if (path.includes("/studio/formats")) return Response.json([])
    return Response.json(lists[Math.min(listed++, lists.length - 1)])
  })
  vi.stubGlobal("fetch", fetchMock)
  return { stream, listReads: () => listed }
}

/** Each hook with its own query cache, as the app gives it one. */
function renderHook<Result, Props>(
  hook: (props: Props) => Result,
  options?: { initialProps: Props }
) {
  const client = createQueryClient()
  return renderBareHook(hook, {
    ...options,
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  })
}

type Studio = { current: ReturnType<typeof useStudio> }

/** The list as it was at mount, then the workspace saying it changed. */
async function reportChange(api: ReturnType<typeof studioApi>, studio: Studio) {
  await waitFor(() => expect(studio.current.isLoading).toBe(false))
  api.stream.connected()
  api.stream.artifactsChanged([1])
  await waitFor(() => expect(api.listReads()).toBe(2))
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
})

describe("useStudio", () => {
  it("updates the list when the workspace reports a change, without a timer", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] })
    const api = studioApi([[artifact()], [artifact({ status: "ready" })]])

    const { result } = renderHook(() => useStudio(1))
    await vi.waitFor(() => expect(result.current.isLoading).toBe(false))
    api.stream.connected()
    api.stream.artifactsChanged([1])

    await vi.waitFor(() =>
      expect(result.current.artifacts[0]?.status).toBe("ready")
    )
    expect(toast.success).toHaveBeenCalledExactlyOnceWith(
      "Summary of the source is ready"
    )
  })

  it("reads a running list again after a while, in case a notice was lost", async () => {
    vi.useFakeTimers({
      toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"],
    })
    const api = studioApi([[artifact()], [artifact({ status: "ready" })]])

    const { result } = renderHook(() => useStudio(1))
    await vi.waitFor(() => expect(result.current.isLoading).toBe(false))
    await vi.advanceTimersByTimeAsync(10_000)

    await vi.waitFor(() =>
      expect(result.current.artifacts[0]?.status).toBe("ready")
    )
    // Nothing left running, so nothing is read again.
    await vi.advanceTimersByTimeAsync(60_000)
    expect(api.listReads()).toBe(2)
  })

  it("keeps the newest read of the list when an older one lands after it", async () => {
    const stream = eventStream()
    let answerFirstRead!: (response: Response) => void
    let listed = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.endsWith("/events")) return stream.response
        if (path.includes("/studio/formats")) return Response.json([])
        if (listed++ === 0) {
          return new Promise<Response>((resolve) => {
            answerFirstRead = resolve
          })
        }
        return Response.json([artifact({ status: "ready" })])
      })
    )

    const { result } = renderHook(() => useStudio(1))
    await waitFor(() => expect(listed).toBe(1))
    stream.connected()
    stream.artifactsChanged([1])
    await waitFor(() =>
      expect(result.current.artifacts[0]?.status).toBe("ready")
    )
    answerFirstRead(Response.json([artifact()]))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.artifacts[0]?.status).toBe("ready")
  })

  it("shows a success toast once a running artifact turns ready", async () => {
    const api = studioApi([[artifact()], [artifact({ status: "ready" })]])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledExactlyOnceWith(
        "Summary of the source is ready"
      )
    )

    // Nothing left running, so no further read — and no repeat toast.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(api.listReads()).toBe(2)
    expect(toast.success).toHaveBeenCalledOnce()
  })

  it("does not toast for an artifact that was already ready", async () => {
    const api = studioApi([
      [
        artifact({ status: "ready" }),
        artifact({ id: 2, status: "processing" }),
      ],
      [artifact({ status: "ready" }), artifact({ id: 2, status: "ready" })],
    ])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledExactlyOnceWith(
        "Summary of the source is ready"
      )
    )
  })

  it("shows an error toast once a running artifact fails, without the raw error", async () => {
    const api = studioApi([
      [artifact()],
      // A real backend failure here is often a multi-line HTTP exception —
      // that belongs in the row's own tooltip, never pasted into a toast.
      [
        artifact({
          status: "failed",
          error_message:
            "HTTPStatusError: Client error '401 Unauthorized' for url '...'",
        }),
      ],
    ])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledExactlyOnceWith(
        "Summary of the source failed",
        expect.objectContaining({
          description:
            "This artifact couldn’t be generated. Retry it from the artifacts tab.",
        })
      )
    )
    const [, options] = vi.mocked(toast.error).mock.calls[0]
    expect(String(options?.description)).not.toContain("HTTPStatusError")
    expect(toast.success).not.toHaveBeenCalled()

    // Nothing left running, so no further read — and no repeat toast.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(api.listReads()).toBe(2)
    expect(toast.error).toHaveBeenCalledOnce()
  })

  it("shows the same friendly description even with no error message at all", async () => {
    const api = studioApi([
      [artifact()],
      [artifact({ status: "failed", error_message: null })],
    ])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledExactlyOnceWith(
        "Summary of the source failed",
        expect.objectContaining({
          description:
            "This artifact couldn’t be generated. Retry it from the artifacts tab.",
        })
      )
    )
  })

  it("does not toast when a running artifact is cancelled", async () => {
    const api = studioApi([[artifact()], [artifact({ status: "cancelled" })]])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(result.current.artifacts[0]?.status).toBe("cancelled")
    )
    expect(toast.error).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
  })
})

describe("useStudio formats freshness", () => {
  it("asks again for the formats when the selected model changes", async () => {
    // Availability is decided by the server from what is selected, and the
    // client holds the answer. Without re-asking, choosing a chat model leaves
    // every Studio tile disabled until the page is reloaded.
    const fetchMock = vi.fn<(path: RequestInfo | URL) => Promise<Response>>(
      async () => Response.json([])
    )
    vi.stubGlobal("fetch", fetchMock)

    const { rerender } = renderHook(
      ({ token }: { token: string }) => useStudio(1, token),
      { initialProps: { token: "none" } }
    )

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([path]) =>
          String(path).includes("/studio/formats")
        )
      ).toHaveLength(1)
    )

    rerender({ token: "llamacpp:Qwen3-4B-Q4_K_M" })

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([path]) =>
          String(path).includes("/studio/formats")
        )
      ).toHaveLength(2)
    )
  })
})
