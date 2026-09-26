import { afterEach, describe, expect, it, vi } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { toast } from "sonner"

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

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
})

describe("useStudio", () => {
  it("shows a success toast once a running artifact turns ready", async () => {
    const responses: unknown[] = [
      [], // GET /studio/formats
      [artifact()], // GET /artifacts (initial load, still processing)
      [artifact({ status: "ready" })], // GET /artifacts (poll, now ready)
    ]
    const fetchMock = vi.fn(async () => Response.json(responses.shift() ?? []))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useStudio(1))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 4000,
    })

    expect(toast.success).toHaveBeenCalledExactlyOnceWith(
      "Summary of the source is ready"
    )

    // Nothing left running, so no further poll — and no repeat toast.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(toast.success).toHaveBeenCalledOnce()
  }, 8000)

  it("does not toast for an artifact that was already ready", async () => {
    const responses: unknown[] = [
      [], // formats
      [
        artifact({ status: "ready" }),
        artifact({ id: 2, status: "processing" }),
      ],
      [artifact({ status: "ready" }), artifact({ id: 2, status: "ready" })],
    ]
    const fetchMock = vi.fn(async () => Response.json(responses.shift() ?? []))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useStudio(1))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 4000,
    })

    expect(toast.success).toHaveBeenCalledExactlyOnceWith(
      "Summary of the source is ready"
    )
  }, 8000)

  it("shows an error toast once a running artifact fails, without the raw error", async () => {
    const responses: unknown[] = [
      [], // GET /studio/formats
      [artifact()], // GET /artifacts (initial load, still processing)
      // A real backend failure here is often a multi-line HTTP exception —
      // that belongs in the row's own tooltip, never pasted into a toast.
      [
        artifact({
          status: "failed",
          error_message:
            "HTTPStatusError: Client error '401 Unauthorized' for url '...'",
        }),
      ],
    ]
    const fetchMock = vi.fn(async () => Response.json(responses.shift() ?? []))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useStudio(1))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 4000,
    })

    expect(toast.error).toHaveBeenCalledExactlyOnceWith(
      "Summary of the source failed",
      expect.objectContaining({
        description:
          "This artifact couldn’t be generated. Retry it from the artifacts tab.",
      })
    )
    const [, options] = vi.mocked(toast.error).mock.calls[0]
    expect(String(options?.description)).not.toContain("HTTPStatusError")
    expect(toast.success).not.toHaveBeenCalled()

    // Nothing left running, so no further poll — and no repeat toast.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(toast.error).toHaveBeenCalledOnce()
  }, 8000)

  it("shows the same friendly description even with no error message at all", async () => {
    const responses: unknown[] = [
      [],
      [artifact()],
      [artifact({ status: "failed", error_message: null })],
    ]
    const fetchMock = vi.fn(async () => Response.json(responses.shift() ?? []))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useStudio(1))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 4000,
    })

    expect(toast.error).toHaveBeenCalledExactlyOnceWith(
      "Summary of the source failed",
      expect.objectContaining({
        description:
          "This artifact couldn’t be generated. Retry it from the artifacts tab.",
      })
    )
  }, 8000)

  it("does not toast when a running artifact is cancelled", async () => {
    const responses: unknown[] = [
      [],
      [artifact()],
      [artifact({ status: "cancelled" })],
    ]
    const fetchMock = vi.fn(async () => Response.json(responses.shift() ?? []))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useStudio(1))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3), {
      timeout: 4000,
    })

    expect(toast.error).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
  }, 8000)
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
