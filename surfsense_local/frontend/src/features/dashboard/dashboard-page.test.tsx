import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { DETAIL_RAIL_WIDTH, MAIN_RAIL_WIDTH } from "@/components/ui/slide-rail"
import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { readSourcePreview, RIGHT_PANEL_KEY } from "./chrome-prefs"
import { DashboardPage } from "./dashboard-page"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

function rememberOpenThread(workspaceId: number, threadId: number) {
  localStorage.setItem(
    `surfsense:last-thread:${workspaceId}:v1`,
    String(threadId)
  )
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
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
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  })
  vi.stubGlobal("surfsense", {
    apiUrl: "",
    platform: "darwin",
    openDocument: vi.fn(async () => ""),
    revealDocument: vi.fn(async () => ""),
  })
})

describe("dashboard chat", () => {
  it("renames a saved chat from the conversation title", async () => {
    const thread = {
      id: 10,
      workspace_id: 1,
      title: "Original title",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([thread])
        }
        if (path === "/chat/threads/10/messages") {
          return Response.json([])
        }
        if (
          path === "/chat/threads/10" &&
          init?.method === "PATCH" &&
          typeof init.body === "string"
        ) {
          return Response.json({
            ...thread,
            title: JSON.parse(init.body).title,
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    rememberOpenThread(1, 10)

    render(
      <ThemeProvider>
        <TooltipProvider>
          <DashboardPage
            initialProviderAvailable={true}
            selection={{
              model_type: "text_gen",
              provider: "llamacpp",
              connection_id: null,
              name: "llama3.2:1b",
              updated_at: "2026-09-05T00:00:00Z",
            }}
            initialWorkspaces={[workspace]}
            onModelSelected={vi.fn()}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    const conversation = screen.getByRole("region", { name: "Conversation" })
    await user.click(
      await within(conversation).findByRole("button", {
        name: "Original title",
      })
    )
    const input = within(conversation).getByRole("textbox", {
      name: "Chat name",
    })
    await user.clear(input)
    await user.type(input, "Banking fees{Enter}")

    expect(
      await within(conversation).findByRole("button", { name: "Banking fees" })
    ).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith(
      "/chat/threads/10",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "Banking fees" }),
      })
    )

    await user.click(screen.getByRole("button", { name: "Open settings" }))
    expect(screen.getByRole("heading", { name: "Appearance" })).toBeTruthy()
  })

  it("focuses the composer when opening a chat, not the title", async () => {
    const thread = {
      id: 10,
      workspace_id: 1,
      title: "Original title",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([thread])
        }
        if (path === "/chat/threads/10/messages") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()
    rememberOpenThread(1, 10)

    render(
      <ThemeProvider>
        <TooltipProvider>
          <DashboardPage
            initialProviderAvailable={true}
            selection={{
              model_type: "text_gen",
              provider: "llamacpp",
              connection_id: null,
              name: "llama3.2:1b",
              updated_at: "2026-09-05T00:00:00Z",
            }}
            initialWorkspaces={[workspace]}
            onModelSelected={vi.fn()}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    const conversation = screen.getByRole("region", { name: "Conversation" })
    await waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole("textbox", { name: "Message" })
      )
    })
    expect(
      within(conversation).getByRole("button", { name: "Original title" })
    ).not.toBe(document.activeElement)

    await user.click(screen.getByRole("button", { name: "New chat" }))
    await waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole("textbox", { name: "Message" })
      )
    })

    // Past chats live behind the "Chats" dialog now.
    await user.click(screen.getByRole("button", { name: "Chats" }))
    await user.click(
      await screen.findByRole("button", { name: "Original title" })
    )
    await waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole("textbox", { name: "Message" })
      )
    })
  })

  it("keeps the composer focused on a keyboard switch and names the conversation to it", async () => {
    const thread = {
      id: 10,
      workspace_id: 1,
      title: "Original title",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([thread])
        }
        if (path === "/chat/threads/10/messages") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()
    rememberOpenThread(1, 10)

    render(
      <ThemeProvider>
        <TooltipProvider>
          <DashboardPage
            initialProviderAvailable={true}
            selection={{
              model_type: "text_gen",
              provider: "llamacpp",
              connection_id: null,
              name: "llama3.2:1b",
              updated_at: "2026-09-05T00:00:00Z",
            }}
            initialWorkspaces={[workspace]}
            onModelSelected={vi.fn()}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    await waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole("textbox", { name: "Message" })
      )
    })
    await user.click(screen.getByRole("button", { name: "New chat" }))

    // A keyboard user is told where they landed; a click keeps the composer.
    await user.click(screen.getByRole("button", { name: "Chats" }))
    ;(await screen.findByRole("button", { name: "Original title" })).focus()
    await user.keyboard("{Enter}")

    // Focus stays where someone can type; the composer is described by the
    // conversation's heading, so a screen reader still says where it landed.
    const composer = screen.getByRole("textbox", { name: "Message" })
    await waitFor(() => {
      expect(document.activeElement).toBe(composer)
      const describedBy = composer.getAttribute("aria-describedby")
      expect(
        describedBy && document.getElementById(describedBy)?.textContent
      ).toBe("Original title")
    })
  })

  it("never announces a reply finished for one left mid-stream in another chat", async () => {
    const encoder = new TextEncoder()
    const cached = {
      id: 11,
      workspace_id: 1,
      title: "Cached chat",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    const streaming = { ...cached, id: 10, title: "Streaming chat" }
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([cached, streaming])
        }
        if (path === "/chat/threads/11/messages") {
          return Response.json([
            {
              id: 1,
              role: "user",
              content: { text: "Earlier question" },
              created_at: "2026-09-05T00:00:00Z",
              completed_at: null,
            },
            {
              id: 2,
              role: "assistant",
              content: { text: "Earlier answer", citations: [] },
              created_at: "2026-09-05T00:00:01Z",
              completed_at: "2026-09-05T00:00:01Z",
            },
          ])
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          // Answers, then never finishes, as a model still generating.
          return new Response(
            new ReadableStream({
              start(controller) {
                controller.enqueue(
                  encoder.encode(
                    'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"delta","text":"Partial answer"}\n\n'
                  )
                )
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        if (path === "/chat/threads/10/messages") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()
    rememberOpenThread(1, 11)

    render(
      <ThemeProvider>
        <TooltipProvider>
          <DashboardPage
            initialProviderAvailable={true}
            selection={{
              model_type: "text_gen",
              provider: "llamacpp",
              connection_id: null,
              name: "llama3.2:1b",
              updated_at: "2026-09-05T00:00:00Z",
            }}
            initialWorkspaces={[workspace]}
            onModelSelected={vi.fn()}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    expect(await screen.findByText("Earlier answer")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Chats" }))
    await user.click(
      await screen.findByRole("button", { name: "Streaming chat" })
    )
    await user.type(
      await screen.findByRole("textbox", { name: "Message" }),
      "Still going?"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))
    expect(await screen.findByText("Partial answer")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Chats" }))
    await user.click(await screen.findByRole("button", { name: "Cached chat" }))
    expect(await screen.findByText("Earlier answer")).toBeTruthy()

    expect(
      screen
        .queryAllByRole("status")
        .some((status) => status.textContent === "Reply finished")
    ).toBe(false)
  })

  it("keeps composer placement aligned with the conversation lifecycle", async () => {
    let resolveThreads!: (response: Response) => void
    let resolveCreate!: (response: Response) => void
    const threadsResponse = new Promise<Response>((resolve) => {
      resolveThreads = resolve
    })
    const createResponse = new Promise<Response>((resolve) => {
      resolveCreate = resolve
    })
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads" && !init?.method) {
          return threadsResponse
        }
        if (path === "/workspaces/1/chat/threads" && init?.method === "POST") {
          return createResponse
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          return new Response(
            'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"completed","assistant_completed_at":"2026-09-05T00:00:01Z"}\n\ndata: [DONE]\n\n',
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        if (path === "/chat/threads/10/messages") {
          return Response.json([
            {
              id: 100,
              role: "user",
              content: { text: "Start a chat" },
              created_at: "2026-09-05T00:00:00Z",
              completed_at: null,
            },
            {
              id: 101,
              role: "assistant",
              content: { text: "", citations: [] },
              created_at: "2026-09-05T00:00:01Z",
              completed_at: "2026-09-05T00:00:01Z",
            },
          ])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    const conversationWhileLoading = screen.getByRole("region", {
      name: "Conversation",
    })
    expect(await screen.findByRole("textbox", { name: "Message" })).toBeTruthy()
    expect(
      conversationWhileLoading.querySelector('[data-slot="skeleton"]')
    ).toBeNull()
    expect(screen.queryByRole("heading", { name: "New chat" })).toBeNull()

    resolveThreads(Response.json([]))
    const input = await screen.findByRole("textbox", { name: "Message" })
    const addSources = screen.getByRole("button", {
      name: "Attach images",
    })
    expect(screen.queryByRole("heading", { name: "New chat" })).toBeNull()
    expect(input.closest('[data-composer-placement="center"]')).toBeTruthy()
    expect(
      addSources.closest('[data-composer-placement="center"]')
    ).toBeTruthy()
    expect(addSources.getAttribute("data-slot")).toBe("tooltip-trigger")
    expect(addSources.className).not.toContain("-mr-1.5")
    const conversation = screen.getByRole("region", { name: "Conversation" })
    const viewport = conversation.querySelector("[data-chat-viewport]")
    expect(conversation.parentElement?.className).toContain("flex-1")
    expect(conversation.querySelector("header")).toBeTruthy()
    // Top edge only, so the sticky composer at the bottom is never masked.
    expect(viewport?.className).toContain("scroll-fade-t")

    await user.type(input, "Start a chat")
    await user.click(screen.getByRole("button", { name: "Send message" }))
    await waitFor(() => {
      const bottomComposer = screen
        .getByRole("textbox", { name: "Message" })
        .closest('[data-composer-placement="bottom"]')
      expect(bottomComposer).toBeTruthy()
      expect(bottomComposer?.closest("[data-chat-viewport]")).toBeTruthy()
      expect(
        screen
          .getByRole("button", { name: "Attach images" })
          .closest('[data-composer-placement="bottom"]')
      ).toBeTruthy()
      expect(
        screen.getByRole("button", {
          name: "Attach images",
        }).className
      ).toContain("-mr-1.5")
    })

    resolveCreate(
      Response.json(
        {
          id: 10,
          workspace_id: 1,
          title: "Start a chat",
          created_at: "2026-09-05T00:00:00Z",
          updated_at: "2026-09-05T00:00:00Z",
        },
        { status: 201 }
      )
    )
    await within(
      screen.getByRole("region", { name: "Conversation" })
    ).findByRole("button", { name: "Start a chat" })
    await waitFor(() => {
      expect(document.querySelectorAll("time")).toHaveLength(1)
    })
    expect(
      screen
        .getByRole("textbox", { name: "Message" })
        .closest('[data-composer-placement="bottom"]')
    ).toBeTruthy()

    const activeInput = await screen.findByRole("textbox", { name: "Message" })
    await screen.findByRole("button", { name: "Send message" })
    await user.type(activeInput, "Discard this draft")
    await user.click(screen.getByRole("button", { name: "New chat" }))

    await waitFor(() => {
      const resetInput = screen.getByRole("textbox", { name: "Message" })
      expect(
        resetInput.closest('[data-composer-placement="center"]')
      ).toBeTruthy()
      expect((resetInput as HTMLTextAreaElement).value).toBe("")
    })
  })

  it("keeps a new chat after remount", async () => {
    const thread = {
      id: 10,
      workspace_id: 1,
      title: "Original title",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (
        path === "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
      ) {
        return Response.json([])
      }
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/chat/threads/10/messages") return Response.json([])
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    rememberOpenThread(1, 10)
    const page = (
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    render(page)
    expect(
      await within(
        screen.getByRole("region", { name: "Conversation" })
      ).findByRole("button", { name: "Original title" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "New chat" }))
    await waitFor(() => {
      expect(
        screen
          .getByRole("textbox", { name: "Message" })
          .closest('[data-composer-placement="center"]')
      ).toBeTruthy()
    })
    expect(
      within(screen.getByRole("region", { name: "Conversation" })).queryByRole(
        "button",
        { name: "Original title" }
      )
    ).toBeNull()

    cleanup()
    render(page)
    const input = await screen.findByRole("textbox", { name: "Message" })
    expect(input.closest('[data-composer-placement="center"]')).toBeTruthy()
    expect(
      within(screen.getByRole("region", { name: "Conversation" })).queryByRole(
        "button",
        { name: "Original title" }
      )
    ).toBeNull()
  })

  it("shows message skeletons only while a loaded chat’s messages load", async () => {
    const thread = {
      id: 10,
      workspace_id: 1,
      title: "Original title",
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    let resolveMessages!: (response: Response) => void
    const messagesResponse = new Promise<Response>((resolve) => {
      resolveMessages = resolve
    })
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads")
          return Response.json([thread])
        if (path === "/chat/threads/10/messages") return messagesResponse
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    rememberOpenThread(1, 10)

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    const conversation = screen.getByRole("region", { name: "Conversation" })
    await waitFor(() => {
      expect(conversation.querySelector('[data-slot="skeleton"]')).toBeTruthy()
    })
    expect(
      screen
        .queryByRole("textbox", { name: "Message" })
        ?.closest('[data-composer-placement="center"]')
    ).toBeNull()

    resolveMessages(Response.json([]))
    await waitFor(() => {
      expect(conversation.querySelector('[data-slot="skeleton"]')).toBeNull()
    })
    expect(
      screen
        .getByRole("textbox", { name: "Message" })
        .closest('[data-composer-placement="bottom"]')
    ).toBeTruthy()
  })

  it("creates a thread on first send and scopes retrieval to selected sources", async () => {
    let messageSent = false
    let messageReads = 0
    let resolveCanonical!: (response: Response) => void
    const canonicalResponse = new Promise<Response>((resolve) => {
      resolveCanonical = resolve
    })
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
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
        if (path.includes("/documents/by-chunk/30")) {
          return Response.json({
            id: 20,
            title: "Guide.txt",
            document_type: "FILE",
            workspace_id: 1,
            chunks: [
              {
                id: 30,
                content: "indexed passage",
                position: 0,
                start_line: 1,
                end_line: 2,
              },
            ],
            total_chunks: 1,
            chunk_start_index: 0,
          })
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          messageSent = true
          return new Response(
            'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"citation-catalog","items":[{"source_id":1,"chunk_id":30,"document_id":20,"start_line":1,"end_line":2}]}\n\ndata: {"type":"delta","text":"Grounded answer [1]"}\n\ndata: {"type":"citations","items":[{"source_id":1,"chunk_id":30,"document_id":20,"start_line":1,"end_line":2}]}\n\ndata: {"type":"completed","assistant_completed_at":"2026-09-05T00:00:01Z","text":"Grounded answer [citation:30]"}\n\ndata: [DONE]\n\n',
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        if (path === "/chat/threads/10/messages" && !init?.method) {
          if (!messageSent) {
            return Response.json([])
          }
          messageReads += 1
          if (messageReads === 1) {
            return canonicalResponse
          }
          return Response.json([
            {
              id: 100,
              role: "user",
              content: { text: "What is indexed?" },
              created_at: "2026-09-05T00:00:00Z",
              completed_at: null,
            },
            {
              id: 101,
              role: "assistant",
              content: {
                text: "Grounded answer [citation:30]",
                citations: [
                  {
                    source_id: 1,
                    chunk_id: 30,
                    document_id: 20,
                    start_line: 1,
                    end_line: 2,
                  },
                ],
              },
              created_at: "2026-09-05T00:00:01Z",
              completed_at: "2026-09-05T00:00:01Z",
            },
          ])
        }
        return Response.json({ detail: `Unhandled ${path}` }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.click(screen.getByRole("button", { name: "New chat" }))
    await screen.findByRole("checkbox", { name: "Select Guide.txt" })
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
    fireEvent.click(screen.getByRole("button", { name: "View cited chunk 30" }))
    expect(await screen.findByText("indexed passage")).toBeTruthy()
    expect(screen.getByText("Cited chunk")).toBeTruthy()
    const rail = document.querySelector("#workspace-right-panel")?.parentElement
      ?.parentElement
    expect(rail).toBeInstanceOf(HTMLElement)
    expect((rail as HTMLElement).style.width).toBe(`${DETAIL_RAIL_WIDTH}px`)
    await user.click(screen.getByRole("button", { name: "Open file" }))
    expect(window.surfsense?.openDocument).toHaveBeenCalledWith(1, 20)
    await user.click(screen.getByRole("button", { name: "Close citation" }))
    expect((rail as HTMLElement).style.width).toBe(`${MAIN_RAIL_WIDTH}px`)
    // The right rail has exactly one job once the citation view closes.
    expect(screen.getByRole("heading", { name: "Artifacts" })).toBeTruthy()
    // Sources live in the left sidebar, always visible.
    const sourceButton = await screen.findByRole("button", {
      name: "Guide.txt",
    })
    await user.click(sourceButton)
    expect(window.surfsense?.openDocument).toHaveBeenCalledTimes(2)
    expect(
      fetchMock.mock.calls.some(
        ([path]) => String(path) === "/workspaces/1/documents/20"
      )
    ).toBe(false)
    resolveCanonical(Response.json([]))
    await screen.findByRole("button", { name: "Send message" })
    await waitFor(() => {
      expect(messageReads).toBe(2)
      expect(screen.getByText("Grounded answer")).toBeTruthy()
      expect(document.querySelectorAll("time")).toHaveLength(2)
    })
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
      document_ids: [20],
    })
  })

  it("loads threads and sources for the selected workspace", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
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
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace, secondWorkspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.click(screen.getByRole("button", { name: "Second Workspace" }))

    expect(screen.getByRole("heading", { name: "SurfSense" })).toBeTruthy()
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

  it("previews a PDF in a left rail and restores the right panel preference", async () => {
    const pdf = {
      id: 42,
      title: "report.pdf",
      document_type: "FILE",
      mime_type: "application/pdf",
      status: "pending",
      error_message: null,
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (
        path === "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
      ) {
        return Response.json([pdf])
      }
      if (path === "/workspaces/1/chat/threads") return Response.json([])
      if (path === "/workspaces/1/documents/42/original") {
        return new Response(new Uint8Array([37, 80, 68, 70, 45, 49, 46, 55]))
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    localStorage.setItem(RIGHT_PANEL_KEY, "open")
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await user.click(await screen.findByRole("button", { name: "report.pdf" }))
    expect(
      await screen.findByRole("complementary", { name: "Source preview" })
    ).toBeTruthy()
    const rightRail = document.querySelector("#workspace-right-panel")
      ?.parentElement?.parentElement as HTMLElement
    expect(rightRail.style.width).toBe("0px")
    expect(readSourcePreview(workspace.id)).toBe(42)
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/workspaces/1/documents/42/original",
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      )
    })

    await user.click(
      screen.getByRole("button", { name: "Close source preview" })
    )
    expect(readSourcePreview(workspace.id)).toBeNull()
    expect(rightRail.style.width).toBe(`${MAIN_RAIL_WIDTH}px`)
    expect(localStorage.getItem(RIGHT_PANEL_KEY)).toBe("open")
  })

  it("surfaces a message request failure inside the conversation", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (path === "/llm/selection/text_gen") {
          return Response.json({
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          })
        }
        if (path === "/llm/catalog/local") {
          return Response.json({
            rows: [],
            recommended_id: null,
          })
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
        if (path === "/license/status") {
          return Response.json({ state: "none" })
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
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Fail safely"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    // Failing before the stream has no backend kind, but its useful detail is
    // kept inside the translated fallback. The action stays Retry, never Model setup.
    expect(
      await screen.findByText(
        "Something went wrong generating a reply: Provider crashed"
      )
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Model setup" })).toBeNull()
  })

  it("shows how far the model has read while the stream has no token yet", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (path === "/llm/catalog/local") {
          return Response.json({ rows: [], recommended_id: null })
        }
        if (path === "/workspaces/1/chat/threads" && init?.method === "POST") {
          return Response.json(
            {
              id: 10,
              workspace_id: 1,
              title: "Long read",
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            { status: 201 }
          )
        }
        if (path === "/license/status") {
          return Response.json({ state: "none" })
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          const frames =
            'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"prompt-progress","processed":0,"total":8192}\n\ndata: {"type":"prompt-progress","processed":2048,"total":8192}\n\n'
          // Held open on the progress frame, as a model still reading does.
          return new Response(
            new ReadableStream({
              start(controller) {
                controller.enqueue(new TextEncoder().encode(frames))
                init.signal?.addEventListener("abort", () =>
                  controller.error(new DOMException("Aborted", "AbortError"))
                )
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        return Response.json([])
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "Qwen3-1.7B-Q4_K_M",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Long read"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    expect(
      await screen.findByRole("button", { name: "Reading 25%" })
    ).toBeTruthy()
    await user.click(
      await screen.findByRole("button", { name: "Stop generating" })
    )
  })

  it("offers no Retry for a context-too-long failure it cannot fix", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
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
              title: "Too long",
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            { status: 201 }
          )
        }
        if (path === "/chat/threads/10/messages" && init?.method === "POST") {
          return new Response(
            'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"error","kind":"context_too_long","message":"context window exceeded","provider":"llamacpp"}\n\ndata: [DONE]\n\n',
            { headers: { "Content-Type": "text/event-stream" } }
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
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Too long"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    expect(
      await screen.findByText(
        "This conversation is too long for the model’s context window. Start a new chat or pick a model with a larger window."
      )
    ).toBeTruthy()
    // Retry resends the identical message to the identical model and fails
    // identically — it cannot fix an oversized context window.
    const retryButton = screen.queryByRole("button", { name: "Retry" })
    expect(retryButton, "context_too_long must not offer Retry").toBeNull()
  })

  it("aborts the active stream when stop is pressed", async () => {
    const captured: { signal: AbortSignal | null } = { signal: null }
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
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
          // Text has arrived when the person stops it.
          return new Response(
            new ReadableStream({
              start(controller) {
                controller.enqueue(
                  new TextEncoder().encode(
                    'data: {"type":"accepted","user_message_id":100,"assistant_message_id":101,"user_created_at":"2026-09-05T00:00:00Z"}\n\ndata: {"type":"delta","text":"Partial answer"}\n\n'
                  )
                )
                captured.signal?.addEventListener("abort", () =>
                  controller.error(new DOMException("Aborted", "AbortError"))
                )
              },
            }),
            { headers: { "Content-Type": "text/event-stream" } }
          )
        }
        if (path === "/chat/threads/10/messages") {
          // The stopped turn as the backend keeps it: the text so far.
          return Response.json(
            captured.signal === null
              ? []
              : [
                  {
                    id: 100,
                    role: "user",
                    content: { text: "Stop this" },
                    created_at: "2026-09-05T00:00:00Z",
                    completed_at: null,
                  },
                  {
                    id: 101,
                    role: "assistant",
                    content: { text: "Partial answer", citations: [] },
                    created_at: "2026-09-05T00:00:00Z",
                    completed_at: "2026-09-05T00:00:01Z",
                  },
                ]
          )
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByRole("textbox", { name: "Message" })
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Stop this"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))
    await screen.findByText("Partial answer")
    await user.click(
      await screen.findByRole("button", { name: "Stop generating" })
    )

    expect(captured.signal?.aborted).toBe(true)
    expect(
      await screen.findByRole("button", { name: "Send message" })
    ).toBeTruthy()
    await screen.findByText("Partial answer")
    // Stopped, not finished: the person chose to end it, so nothing is announced.
    expect(
      screen
        .queryAllByRole("status")
        .some((region) => region.textContent === "Reply finished")
    ).toBe(false)
  })

  it("collapses the right rail from the toolbar outside the card", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([])
        }
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([])
        }
        if (path === "/workspaces/1/artifacts") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TooltipProvider>
          <DashboardPage
            initialProviderAvailable={true}
            selection={{
              model_type: "text_gen",
              provider: "llamacpp",
              connection_id: null,
              name: "llama3.2:1b",
              updated_at: "2026-09-05T00:00:00Z",
            }}
            initialWorkspaces={[workspace]}
            onModelSelected={vi.fn()}
          />
        </TooltipProvider>
      </ThemeProvider>
    )

    expect(
      await screen.findByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "Hide right panel" })
        .closest(".titlebar-controls")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Hide right panel" }))
    expect(
      screen.queryByRole("complementary", { name: "Workspace artifacts" })
    ).toBeNull()
    expect(
      screen.getByRole("button", { name: "Show right panel" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Show right panel" }))
    expect(
      screen.getByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
  })

  it("shows how many sources the chat will use", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
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
            {
              id: 21,
              title: "Notes.txt",
              document_type: "FILE",
              status: "ready",
              error_message: null,
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
            {
              id: 22,
              title: "Draft.txt",
              document_type: "FILE",
              status: "processing",
              error_message: null,
              created_at: "2026-09-05T00:00:00Z",
              updated_at: "2026-09-05T00:00:00Z",
            },
          ])
        }
        if (path === "/workspaces/1/chat/threads") return Response.json([])
        if (path === "/workspaces/1/studio/formats") return Response.json([])
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    // A plain count, not a control: ff1aa3e53 took away its click.
    const count = await screen.findByText("2 sources")
    expect(count.closest('[data-composer-placement="center"]')).toBeTruthy()

    await user.click(screen.getByRole("checkbox", { name: "Select Guide.txt" }))
    expect(screen.getByText("1 source")).toBeTruthy()
  })

  it("opens a generated artifact in the detail rail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "llamacpp", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") {
          return Response.json([])
        }
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "summary",
              label: "Summary",
              requires_model_types: ["text_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/artifacts") {
          return Response.json([
            {
              id: 12,
              document_id: 4,
              format: "summary",
              generation: 1,
              title: "Weekly summary",
              status: "ready",
              error_message: null,
              created_at: "2026-09-06T00:00:00Z",
              updated_at: "2026-09-06T00:00:00Z",
            },
          ])
        }
        if (path === "/artifacts/12") {
          return Response.json({
            id: 12,
            document_id: 4,
            format: "summary",
            generation: 1,
            title: "Weekly summary",
            status: "ready",
            error_message: null,
            content: "Saturn is a gas giant.",
            files: [],
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    expect(screen.getByRole("heading", { name: "Sources" })).toBeTruthy()
    const sourcesPanel = screen.getByRole("complementary", {
      name: "Workspace sources",
    })
    const sourcesScroll = sourcesPanel.querySelector(
      '[data-slot="scroll-fade-viewport"]'
    )
    expect(
      sourcesScroll?.contains(screen.getByRole("heading", { name: "Sources" }))
    ).toBe(false)
    expect(
      sourcesScroll?.contains(screen.getByRole("button", { name: "Add" }))
    ).toBe(false)
    expect(sourcesScroll).toBeTruthy()

    expect(screen.getByRole("heading", { name: "Artifacts" })).toBeTruthy()
    const artifactsPanel = screen.getByRole("complementary", {
      name: "Workspace artifacts",
    })
    const artifactsScroll = artifactsPanel.querySelector(
      '[data-slot="scroll-fade-viewport"]'
    )
    const weeklySummary = await screen.findByRole("button", {
      name: /^Weekly summary/,
    })
    expect(
      artifactsScroll?.contains(
        screen.getByRole("heading", { name: "Artifacts" })
      )
    ).toBe(false)
    expect(artifactsScroll?.contains(weeklySummary)).toBe(true)
    expect(screen.getByRole("button", { name: "Summary" })).toBeTruthy()
    await user.click(weeklySummary)
    expect(await screen.findByText("Saturn is a gas giant.")).toBeTruthy()
    expect(screen.getByRole("complementary", { name: "Artifact" })).toBeTruthy()
    const rail = document.querySelector("#workspace-right-panel")?.parentElement
      ?.parentElement
    expect((rail as HTMLElement).style.width).toBe(`${DETAIL_RAIL_WIDTH}px`)
    await user.click(screen.getByRole("button", { name: "Close artifact" }))
    expect((rail as HTMLElement).style.width).toBe(`${MAIN_RAIL_WIDTH}px`)
    expect(
      screen.getByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Artifacts" })).toBeTruthy()
  })

  it("remembers whether the right rail is open across remounts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (
        path === "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
      ) {
        return Response.json([])
      }
      if (path === "/workspaces/1/chat/threads") return Response.json([])
      if (path === "/workspaces/1/studio/formats") return Response.json([])
      if (path === "/workspaces/1/artifacts") return Response.json([])
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const page = (
      <TooltipProvider>
        <DashboardPage
          initialProviderAvailable={true}
          selection={{
            model_type: "text_gen",
            provider: "llamacpp",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    render(page)
    expect(
      await screen.findByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Hide right panel" }))
    expect(localStorage.getItem(RIGHT_PANEL_KEY)).toBe("collapsed")
    expect(
      screen.queryByRole("complementary", { name: "Workspace artifacts" })
    ).toBeNull()

    cleanup()
    render(page)
    expect(
      screen.queryByRole("complementary", { name: "Workspace artifacts" })
    ).toBeNull()
    expect(
      screen.getByRole("button", { name: "Show right panel" })
    ).toBeTruthy()
  })
  it("shows the egress notice only while a model on the refused host is selected", async () => {
    // Egress is per host: a model on another, allowed host must not inherit
    // the notice, and coming back to the refused one must bring it back.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/connections/1/models") {
          return Response.json(
            {
              detail: {
                code: "egress_disabled",
                message: "sending data to openrouter.ai is off",
                destination: "host:openrouter.ai",
                host: "openrouter.ai",
              },
            },
            { status: 403 }
          )
        }
        if (path === "/llm/connections/2/models") {
          return Response.json([
            {
              connection_id: 2,
              connection_label: "OpenAI",
              name: "gpt-5",
              types: ["text_gen"],
              capability_source: "catalog",
              selectable_for: ["text_gen"],
            },
          ])
        }
        if (path === "/license/status") return Response.json({ state: "none" })
        return Response.json([])
      })
    )
    const onOpenRouter = {
      model_type: "text_gen" as const,
      provider: "openai_compatible",
      connection_id: 1,
      name: "anthropic/claude-fable-5",
      updated_at: "2026-09-05T00:00:00Z",
    }
    const onOpenAI = {
      ...onOpenRouter,
      connection_id: 2,
      name: "gpt-5",
    }
    const page = (selection: typeof onOpenRouter) => (
      <TooltipProvider>
        <DashboardPage
          selection={selection}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )
    const refused = "Sending data to openrouter.ai is off."

    const { rerender } = render(page(onOpenRouter))
    expect(await screen.findByText(refused)).toBeTruthy()

    rerender(page(onOpenAI))
    await waitFor(() => expect(screen.queryByText(refused)).toBeNull())
    expect(
      screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
        .disabled
    ).toBe(false)

    rerender(page(onOpenRouter))
    expect(await screen.findByText(refused)).toBeTruthy()
  })
})
