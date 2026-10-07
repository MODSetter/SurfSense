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
    version: null,
    spec_kind: null,
    refinable: false,
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

  it("keeps a created artifact when a list read started before it lands after", async () => {
    const stream = eventStream()
    let answerSecondRead!: (response: Response) => void
    let listed = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path.endsWith("/events")) return stream.response
        if (path.includes("/studio/formats")) return Response.json([])
        if (init?.method === "POST") {
          return Response.json(artifact({ id: 2, status: "pending" }))
        }
        if (listed++ === 0)
          return Response.json([artifact({ status: "ready" })])
        return new Promise<Response>((resolve) => {
          answerSecondRead = resolve
        })
      })
    )

    const { result } = renderHook(() => useStudio(1))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    stream.connected()
    stream.artifactsChanged([1])
    await waitFor(() => expect(listed).toBe(2))
    await result.current.create({ format: "summary", document_ids: [1] })
    // The read began before the job existed, so its answer lacks it.
    answerSecondRead(Response.json([artifact({ status: "ready" })]))

    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(result.current.artifacts.map((a) => a.id)).toEqual([2, 1])
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

  it("does not toast when the agent’s document script fails", async () => {
    const scriptDocument = {
      format: "docx",
      version: { root_id: 1, number: 1, parent_id: null },
      spec_kind: "python",
      refinable: false,
    } as const
    const api = studioApi([
      [artifact(scriptDocument)],
      [
        artifact({
          ...scriptDocument,
          status: "failed",
          error_message:
            "Script error: AttributeError: 'Document' object has no attribute",
        }),
      ],
    ])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(result.current.artifacts[0]?.status).toBe("failed")
    )
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("toasts when a document script fails for a reason outside it, since a retry can finish it", async () => {
    const scriptDocument = {
      format: "docx",
      version: { root_id: 1, number: 1, parent_id: null },
      spec_kind: "python",
      refinable: false,
    } as const
    const api = studioApi([
      [artifact(scriptDocument)],
      [
        artifact({
          ...scriptDocument,
          status: "failed",
          error_message: "database is locked",
        }),
      ],
    ])

    const { result } = renderHook(() => useStudio(1))
    await reportChange(api, result)

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledExactlyOnceWith(
        "Summary of the source failed",
        expect.anything()
      )
    )
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

describe("useStudio refine", () => {
  const v1 = artifact({
    id: 40,
    format: "docx",
    title: "Quarterly report",
    status: "ready",
    version: { root_id: 40, number: 1, parent_id: null },
    spec_kind: "markdown",
    refinable: true,
  })

  function refineApi(answer: Response) {
    const calls: { path: string; init?: RequestInit }[] = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        calls.push({ path, init })
        if (path.endsWith("/events")) return new Response(null, { status: 204 })
        if (path.includes("/studio/formats")) return Response.json([])
        if (path.endsWith("/refine")) return answer.clone()
        return Response.json([v1])
      })
    )
    return calls
  }

  it("puts the next version in the list as soon as the API takes it", async () => {
    const v2 = {
      ...v1,
      id: 41,
      status: "pending" as const,
      version: { root_id: 40, number: 2, parent_id: 40 },
    }
    const calls = refineApi(Response.json(v2))

    const { result } = renderHook(() => useStudio(1))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    await result.current.refine(40, "Add a chart of the revenue")

    const sent = calls.find((call) => call.path === "/artifacts/40/refine")
    expect(sent?.init?.method).toBe("POST")
    expect(JSON.parse(String(sent?.init?.body))).toEqual({
      instruction: "Add a chart of the revenue",
    })
    await waitFor(() =>
      expect(result.current.artifacts.map((each) => each.id)).toEqual([41, 40])
    )
  })

  it("rejects with the API’s reason and leaves the list as it was", async () => {
    refineApi(
      Response.json(
        { detail: "This document is too long for the selected model." },
        { status: 422 }
      )
    )

    const { result } = renderHook(() => useStudio(1))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(result.current.refine(40, "Shorter")).rejects.toThrow(
      "This document is too long for the selected model."
    )
    expect(result.current.artifacts.map((each) => each.id)).toEqual([40])
  })
})

describe("useStudio decide all", () => {
  it("puts the version accepting every change in the list as soon as the API takes it", async () => {
    const v1 = artifact({
      id: 50,
      format: "docx",
      title: "MSA_Acme (revised)",
      status: "ready",
      version: { root_id: 50, number: 1, parent_id: null },
    })
    const v2 = {
      ...v1,
      id: 51,
      status: "pending" as const,
      version: { root_id: 50, number: 2, parent_id: 50 },
    }
    const calls: { path: string; init?: RequestInit }[] = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        calls.push({ path, init })
        if (path.endsWith("/events")) return new Response(null, { status: 204 })
        if (path.includes("/studio/formats")) return Response.json([])
        if (path.endsWith("/accept-all")) return Response.json(v2)
        return Response.json([v1])
      })
    )

    const { result } = renderHook(() => useStudio(1))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    await result.current.decideAll(50, "accept_all")

    const sent = calls.find(
      (call) => call.path === "/artifacts/50/revisions/accept-all"
    )
    expect(sent?.init?.method).toBe("POST")
    await waitFor(() =>
      expect(result.current.artifacts.map((each) => each.id)).toEqual([51, 50])
    )
  })
})
