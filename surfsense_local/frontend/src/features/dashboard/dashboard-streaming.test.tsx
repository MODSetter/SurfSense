import { createElement, type ComponentType } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen } from "@testing-library/react"

import { ThemeProvider } from "@/components/theme-provider"
import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { DashboardPage } from "./dashboard-page"
import { TEXT_NOTICE_GAP_MS } from "@/features/chat/runs/run-store"

const renders: Record<string, number> = {}

function counted<P extends object>(name: string, Component: ComponentType<P>) {
  return function Counted(props: P) {
    renders[name] = (renders[name] ?? 0) + 1
    return createElement(Component, props)
  }
}

vi.mock("./left-sidebar", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./left-sidebar")>()
  return { ...actual, LeftSidebar: counted("sidebar", actual.LeftSidebar) }
})
vi.mock("@/features/sources/sources-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/sources/sources-panel")>()
  return { ...actual, SourcesPanel: counted("sources", actual.SourcesPanel) }
})
vi.mock("@/features/studio/studio-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/studio/studio-panel")>()
  return { ...actual, StudioPanel: counted("studio", actual.StudioPanel) }
})
vi.mock("@/features/chat/thread-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/chat/thread-panel")>()
  return { ...actual, ThreadPanel: counted("threadPanel", actual.ThreadPanel) }
})
vi.mock("@/features/chat/message", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/chat/message")>()
  return {
    ...actual,
    AssistantMessage: counted("replies", actual.AssistantMessage),
  }
})

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

function stored(id: number, role: "user" | "assistant", text: string) {
  return {
    id,
    role,
    content: { text, citations: [] },
    created_at: "2026-09-05T00:00:00Z",
    completed_at: role === "assistant" ? "2026-09-05T00:00:01Z" : null,
  }
}

let reply: ReadableStreamDefaultController<Uint8Array> | null = null
let seq = 0
function frame(payload: object) {
  seq += 1
  reply!.enqueue(
    new TextEncoder().encode(`id: ${seq}\ndata: ${JSON.stringify(payload)}\n\n`)
  )
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem("surfsense:last-thread:1:v1", "10")
  reply = null
  seq = 0
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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/documents?")) {
        return Response.json([
          {
            id: 1,
            title: "Guide.pdf",
            document_type: "FILE",
            mime_type: "application/pdf",
            status: "ready",
            error_message: null,
            created_at: "2026-09-05T00:00:00Z",
            updated_at: "2026-09-05T00:00:00Z",
            folder_id: null,
          },
        ])
      }
      if (path === "/workspaces/1/chat/threads") {
        return Response.json([
          {
            id: 10,
            workspace_id: 1,
            title: "Quarterly numbers",
            uses_agent: false,
            created_at: "2026-09-05T00:00:00Z",
            updated_at: "2026-09-05T00:00:00Z",
            running: true,
            run_state: { state: "running", position: null },
          },
        ])
      }
      if (path === "/chat/threads/10/messages") {
        return Response.json([
          stored(1, "user", "First question?"),
          stored(2, "assistant", "First answer."),
          stored(3, "user", "Second question?"),
          stored(4, "assistant", "Second answer."),
        ])
      }
      if (path.startsWith("/chat/threads/10/run?after=")) {
        return new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              reply = controller
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } }
        )
      }
      if (path.startsWith("/workspaces/1/events")) {
        return new Response(new ReadableStream())
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

// Past the text notice a frame schedules, which comes no sooner than the gap after the last.
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, TEXT_NOTICE_GAP_MS + 20))
  })

describe("dashboard while a reply streams", () => {
  it("renders each token in the live reply alone", async () => {
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
    await screen.findByText("Second answer.")
    await screen.findByText("Guide.pdf")
    while (!reply) await settle()
    frame({
      type: "accepted",
      user_message_id: 5,
      assistant_message_id: 6,
      user_created_at: "2026-09-05T00:00:00Z",
    })
    frame({ type: "delta", text: "Revenue" })
    await screen.findByText("Revenue")
    await settle()
    const before = { ...renders }

    for (const word of [" climbed", " in", " every", " quarter."]) {
      frame({ type: "delta", text: word })
      await settle()
    }

    expect(screen.getByText("Revenue climbed in every quarter.")).toBeTruthy()
    expect(renders).toEqual(before)
  })
})
