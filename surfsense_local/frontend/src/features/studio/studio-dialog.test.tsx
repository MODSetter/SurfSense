import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { StudioDialog } from "./studio-dialog"

const readyDocument = {
  id: 4,
  title: "Saturn facts",
  document_type: "NOTE" as const,
  status: "ready" as const,
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

const pendingArtifact = {
  id: 9,
  document_id: 20,
  format: "summary",
  generation: 1,
  title: "Summary",
  status: "pending" as const,
  error_message: null,
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
}

beforeEach(() => {
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

describe("studio dialog", () => {
  it("submits a job for the chosen format and sources", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "summary",
              label: "Summary",
              requires_key: false,
              available: true,
            },
          ])
        }
        if (path === "/workspaces/1/studio/jobs" && init?.method === "POST") {
          return Response.json(pendingArtifact, { status: 201 })
        }
        if (path === "/workspaces/1/artifacts") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<StudioDialog workspaceId={1} documents={[readyDocument]} />)

    await user.click(screen.getByRole("button", { name: "Studio" }))
    await user.click(await screen.findByRole("button", { name: "Summary" }))
    await user.click(screen.getByText("Saturn facts"))
    await user.click(screen.getByRole("button", { name: /Generate/ }))

    const jobCall = await vi.waitFor(() =>
      fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/workspaces/1/studio/jobs" && init?.method === "POST"
      )
    )
    expect(JSON.parse(String(jobCall?.[1]?.body))).toEqual({
      format: "summary",
      document_ids: [4],
    })
    expect(await screen.findByText("pending")).toBeTruthy()
  })
})
