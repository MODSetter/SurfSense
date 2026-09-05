import { afterEach, describe, expect, it, vi } from "vitest"
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

describe("dashboard chat", () => {
  it("creates a thread only on first send and streams without a model field", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    )
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
})
