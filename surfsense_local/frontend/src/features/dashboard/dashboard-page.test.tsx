import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"

import { DashboardPage } from "./dashboard-page"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  })
})

describe("dashboard chat", () => {
  it("creates a thread only on first send and streams without a model field", async () => {
    let messageSent = false
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
          ])
        }
        if (path === "/workspaces/1/chat/threads" && !init?.method) {
          return Response.json([])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([
            {
              id: 20,
              title: "Guide.txt",
              document_type: "FILE",
              status: "ready",
              error_message: null,
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
          ])
        }
        if (path === "/workspaces/1/chat/threads" && init?.method === "POST") {
          return Response.json(
            {
              id: 10,
              workspace_id: 1,
              title: "What is indexed?",
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            { status: 201 }
          )
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          messageSent = true
          return new Response(
            'data: {"type":"delta","text":"Grounded "}\n\ndata: {"type":"delta","text":"answer"}\n\ndata: {"type":"citations","items":[{"chunk_id":30,"document_id":20,"start_line":1,"end_line":2}]}\n\ndata: [DONE]\n\n',
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        if (path === "/chat/threads/10/messages" && !init?.method) {
          return Response.json(
            messageSent
              ? [
                  {
                    id: 100,
                    role: "user",
                    content: { text: "What is indexed?" },
                    created_at: "2026-09-05T00:00:00Z",
                  },
                  {
                    id: 101,
                    role: "assistant",
                    content: {
                      text: "Grounded answer",
                      citations: [
                        {
                          chunk_id: 30,
                          document_id: 20,
                          start_line: 1,
                          end_line: 2,
                        },
                      ],
                    },
                    created_at: "2026-09-05T00:00:01Z",
                  },
                ]
              : []
          )
        }
        return Response.json({ detail: `Unhandled ${path}` }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          selection={{
            role: "generation",
            provider: "ollama",
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelRequired={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("No chats yet")
    await user.click(screen.getByRole("button", { name: "New chat" }))
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          path === "/workspaces/1/chat/threads" && init?.method === "POST"
      )
    ).toHaveLength(0)

    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "What is indexed?"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    expect(await screen.findByText("Grounded answer")).toBeTruthy()
    expect(await screen.findByText("Used in answer")).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Source 1: Guide.txt" })
    ).toBeTruthy()
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(
          ([path, init]) =>
            path === "/workspaces/1/chat/threads" && init?.method === "POST"
        )
      ).toHaveLength(1)
    })
    const send = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/chat/threads/10/messages" && init?.method === "POST"
    )
    expect(JSON.parse(String(send?.[1]?.body))).toEqual({
      text: "What is indexed?",
    })
  })

  it("loads threads and sources for the selected workspace", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "ollama", healthy: true, can_download: true },
        ])
      }
      if (path.includes("/chat/threads")) {
        return Response.json([])
      }
      if (path.includes("/documents?")) {
        return Response.json([])
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const secondWorkspace = { ...workspace, id: 2, name: "Second Workspace" }

    render(
      <TooltipProvider>
        <DashboardPage
          selection={{
            role: "generation",
            provider: "ollama",
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace, secondWorkspace]}
          onModelRequired={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("No chats yet")
    await user.click(screen.getByRole("button", { name: "Second Workspace" }))

    expect(
      await screen.findByRole("heading", { name: "Second Workspace" })
    ).toBeTruthy()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/workspaces/2/chat/threads",
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      )
      expect(fetchMock).toHaveBeenCalledWith(
        "/workspaces/2/documents?document_type=FILE&document_type=NOTE",
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      )
    })
  })

  it("surfaces a message request failure inside the conversation", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
          ])
        }
        if (path.endsWith("/documents?document_type=FILE&document_type=NOTE")) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads" && !init?.method) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads" && init?.method === "POST") {
          return Response.json(
            {
              id: 10,
              workspace_id: 1,
              title: "Fail safely",
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            { status: 201 }
          )
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          return Response.json({ detail: "Provider crashed" }, { status: 500 })
        }
        return Response.json([])
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          selection={{
            role: "generation",
            provider: "ollama",
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelRequired={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("No chats yet")
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Fail safely"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    expect(await screen.findByText("Provider crashed")).toBeTruthy()
    expect(screen.getByText("Chat could not continue")).toBeTruthy()
  })

  it("aborts the active stream when stop is pressed", async () => {
    const captured: { signal: AbortSignal | null } = { signal: null }
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
          ])
        }
        if (path.endsWith("/documents?document_type=FILE&document_type=NOTE")) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads" && !init?.method) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads" && init?.method === "POST") {
          return Response.json(
            {
              id: 10,
              workspace_id: 1,
              title: "Stop this",
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            { status: 201 }
          )
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          captured.signal = init.signal ?? null
          return new Response(
            new ReadableStream({
              start(controller) {
                captured.signal?.addEventListener("abort", () =>
                  controller.error(new DOMException("Aborted", "AbortError"))
                )
              },
            })
          )
        }
        if (path === "/chat/threads/10/messages") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          selection={{
            role: "generation",
            provider: "ollama",
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelRequired={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("No chats yet")
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Stop this"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))
    await user.click(
      await screen.findByRole("button", { name: "Stop generating" })
    )

    expect(captured.signal?.aborted).toBe(true)
    expect(
      await screen.findByRole("button", { name: "Send message" })
    ).toBeTruthy()
  })
})
