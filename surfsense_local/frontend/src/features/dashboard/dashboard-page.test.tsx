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

import { RIGHT_TAB_KEY } from "./chrome-prefs"
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
            { name: "ollama", healthy: true, can_download: true },
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
              role: "generation",
              provider: "ollama",
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
            { name: "ollama", healthy: true, can_download: true },
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
              role: "generation",
              provider: "ollama",
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

    await user.click(screen.getByRole("button", { name: "Original title" }))
    await waitFor(() => {
      expect(document.activeElement).toBe(
        screen.getByRole("textbox", { name: "Message" })
      )
    })
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
            { name: "ollama", healthy: true, can_download: true },
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
            role: "generation",
            provider: "ollama",
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
    expect(
      await screen.findByRole("textbox", { name: "Message" })
    ).toBeTruthy()
    expect(
      conversationWhileLoading.querySelector('[data-slot="skeleton"]')
    ).toBeNull()
    expect(screen.queryByRole("heading", { name: "New chat" })).toBeNull()

    resolveThreads(Response.json([]))
    const input = await screen.findByRole("textbox", { name: "Message" })
    const addSources = screen.getByRole("button", { name: "Add sources" })
    expect(screen.queryByRole("heading", { name: "New chat" })).toBeNull()
    expect(input.closest('[data-composer-placement="center"]')).toBeTruthy()
    expect(
      addSources.closest('[data-composer-placement="center"]')
    ).toBeTruthy()
    expect(addSources.getAttribute("data-slot")).toBe("tooltip-trigger")
    expect(addSources.className).not.toContain("-mr-1.5")
    const conversation = screen.getByRole("region", { name: "Conversation" })
    const viewport = conversation.querySelector("[data-chat-viewport]")
    const topShadow = conversation.querySelector(
      '[data-slot="scroll-shadow-top"]'
    )
    expect(conversation.parentElement?.className).toContain("flex-1")
    expect(conversation.querySelector("header")).toBeTruthy()
    expect(topShadow).toBeTruthy()
    expect(
      conversation.querySelector('[data-slot="scroll-shadow-bottom"]')
    ).toBeNull()
    Object.defineProperties(viewport, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, value: 800 },
      scrollTop: { configurable: true, value: 0, writable: true },
    })
    fireEvent.scroll(viewport as HTMLElement)
    expect(topShadow?.className).toContain("opacity-0")
    ;(viewport as HTMLElement).scrollTop = 80
    fireEvent.scroll(viewport as HTMLElement)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-100")
    })

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
          .getByRole("button", { name: "Add sources" })
          .closest('[data-composer-placement="bottom"]')
      ).toBeTruthy()
      expect(
        screen.getByRole("button", { name: "Add sources" }).className
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
    await within(screen.getByRole("region", { name: "Conversation" })).findByRole(
      "button",
      { name: "Start a chat" }
    )
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
          { name: "ollama", healthy: true, can_download: true },
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
            role: "generation",
            provider: "ollama",
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
      await within(screen.getByRole("region", { name: "Conversation" })).findByRole(
        "button",
        { name: "Original title" }
      )
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
            { name: "ollama", healthy: true, can_download: true },
          ])
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([])
        }
        if (path === "/workspaces/1/chat/threads") return Response.json([thread])
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
            role: "generation",
            provider: "ollama",
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
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("Start a conversation to see it here")
    await user.click(screen.getByRole("button", { name: "New chat" }))
    await user.click(
      await screen.findByRole("checkbox", { name: "Select Guide.txt" })
    )
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
    await user.click(screen.getByRole("tab", { name: "Artifacts" }))
    fireEvent.click(screen.getByRole("button", { name: "View cited chunk 30" }))
    expect(await screen.findByText("indexed passage")).toBeTruthy()
    expect(screen.getByText("Cited chunk")).toBeTruthy()
    const rail = document.querySelector("[data-slot=slide-rail]")
    expect(rail).toBeInstanceOf(HTMLElement)
    expect((rail as HTMLElement).style.width).toBe(`${DETAIL_RAIL_WIDTH}px`)
    await user.click(screen.getByRole("button", { name: "Open file" }))
    expect(window.surfsense?.openDocument).toHaveBeenCalledWith(1, 20)
    await user.click(screen.getByRole("button", { name: "Close citation" }))
    expect((rail as HTMLElement).style.width).toBe(`${MAIN_RAIL_WIDTH}px`)
    expect(
      screen
        .getByRole("tab", { name: "Artifacts" })
        .getAttribute("aria-selected")
    ).toBe("true")
    await user.click(screen.getByRole("tab", { name: "Sources" }))
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
          initialProviderAvailable={true}
          selection={{
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace, secondWorkspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("Start a conversation to see it here")
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

  it("surfaces a message request failure inside the conversation", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
          ])
        }
        if (path === "/llm/selection/generation") {
          return Response.json({
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          })
        }
        if (path === "/llm/catalog") {
          return Response.json({
            hardware: null,
            llmfit_version: "1.1.11",
            recommended: [],
            explore: [],
            installed: [],
            warnings: [],
            runtime_status: {},
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
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("Start a conversation to see it here")
    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Fail safely"
    )
    await user.click(screen.getByRole("button", { name: "Send message" }))

    expect(await screen.findByText("Provider crashed")).toBeTruthy()
    expect(screen.getByText("Chat could not continue")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Model setup" }))
    expect(await screen.findByRole("heading", { name: "Models" })).toBeTruthy()
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
          initialProviderAvailable={true}
          selection={{
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: "llama3.2:1b",
            updated_at: "2026-09-05T00:00:00Z",
          }}
          initialWorkspaces={[workspace]}
          onModelSelected={vi.fn()}
        />
      </TooltipProvider>
    )

    await screen.findByText("Start a conversation to see it here")
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

  it("collapses the sources panel from the toolbar outside the card", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
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
              role: "generation",
              provider: "ollama",
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
      await screen.findByRole("complementary", { name: "Workspace sources" })
    ).toBeTruthy()
    expect(
      screen
        .getByRole("button", { name: "Hide right panel" })
        .closest(".titlebar-controls")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Hide right panel" }))
    expect(
      screen.queryByRole("complementary", { name: "Workspace sources" })
    ).toBeNull()
    expect(
      screen.getByRole("button", { name: "Show right panel" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Show right panel" }))
    expect(
      screen.getByRole("complementary", { name: "Workspace sources" })
    ).toBeTruthy()
  })

  it("opens a generated artifact in the detail rail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            { name: "ollama", healthy: true, can_download: true },
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
              requires_role: "generation",
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
            role: "generation",
            provider: "ollama",
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
      '[data-state="active"] [data-slot="scroll-shadow-viewport"]'
    )
    expect(
      sourcesScroll?.contains(screen.getByRole("heading", { name: "All sources" }))
    ).toBe(false)
    expect(
      sourcesScroll?.contains(screen.getByRole("button", { name: "Add" }))
    ).toBe(false)
    expect(sourcesScroll).toBeTruthy()
    await user.click(screen.getByRole("tab", { name: "Artifacts" }))
    expect(screen.getByRole("heading", { name: "Artifacts" })).toBeTruthy()
    expect(
      screen.getByRole("heading", { name: "All generated artifacts" })
    ).toBeTruthy()
    const artifactsPanel = screen.getByRole("complementary", {
      name: "Workspace artifacts",
    })
    const artifactsScroll = artifactsPanel.querySelector(
      '[data-state="active"] [data-slot="scroll-shadow-viewport"]'
    )
    const weeklySummary = await screen.findByRole("button", {
      name: /^Weekly summary/,
    })
    expect(
      artifactsScroll?.contains(
        screen.getByRole("heading", { name: "All generated artifacts" })
      )
    ).toBe(false)
    expect(artifactsScroll?.contains(weeklySummary)).toBe(true)
    expect(screen.queryByRole("heading", { name: "All sources" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Add" })).toBeNull()
    expect(screen.getByRole("button", { name: "Summary" })).toBeTruthy()
    await user.click(weeklySummary)
    expect(await screen.findByText("Saturn is a gas giant.")).toBeTruthy()
    expect(screen.getByRole("complementary", { name: "Artifact" })).toBeTruthy()
    const rail = document.querySelector("[data-slot=slide-rail]")
    expect((rail as HTMLElement).style.width).toBe(`${DETAIL_RAIL_WIDTH}px`)
    await user.click(screen.getByRole("button", { name: "Close artifact" }))
    expect((rail as HTMLElement).style.width).toBe(`${MAIN_RAIL_WIDTH}px`)
    expect(
      screen.getByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
    expect(
      screen
        .getByRole("tab", { name: "Artifacts" })
        .getAttribute("aria-selected")
    ).toBe("true")
  })

  it("remembers the sources and artifacts tab across remounts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "ollama", healthy: true, can_download: true },
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
            role: "generation",
            provider: "ollama",
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
      await screen.findByRole("complementary", { name: "Workspace sources" })
    ).toBeTruthy()
    await user.click(screen.getByRole("tab", { name: "Artifacts" }))
    expect(localStorage.getItem(RIGHT_TAB_KEY)).toBe("artifacts")
    expect(
      screen.getByRole("tab", { name: "Artifacts" }).getAttribute("aria-selected")
    ).toBe("true")

    cleanup()
    render(page)
    expect(
      await screen.findByRole("complementary", { name: "Workspace artifacts" })
    ).toBeTruthy()
    expect(
      screen.getByRole("tab", { name: "Artifacts" }).getAttribute("aria-selected")
    ).toBe("true")
  })
})
