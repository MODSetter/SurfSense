import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { beginRun, updatePair } from "@/features/chat/runs/run-store"
import { render } from "@/test-utils"

import { DashboardPage } from "./dashboard-page"

// Renders that came from the dashboard, not from a component's own state.
const rendered = vi.hoisted(() => ({
  documentRows: 0,
  // Artifact rows, the only ones with a compact time.
  artifactRows: 0,
  studio: 0,
  sidebar: 0,
  thread: 0,
  rightPanel: 0,
}))

vi.mock("@/features/sources/tree/document-row", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/features/sources/tree/document-row")
    >()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    DocumentRow: countRenders(actual.DocumentRow, () => {
      rendered.documentRows += 1
    }),
  }
})
vi.mock("@/components/relative-time", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/components/relative-time")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    RelativeTime: countRenders(actual.RelativeTime, ({ compact }) => {
      if (compact) rendered.artifactRows += 1
    }),
  }
})
vi.mock("@/features/dashboard/left-sidebar", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/dashboard/left-sidebar")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    LeftSidebar: countRenders(actual.LeftSidebar, () => {
      rendered.sidebar += 1
    }),
  }
})
vi.mock("@/features/chat/thread-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/chat/thread-panel")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    ThreadPanel: countRenders(actual.ThreadPanel, () => {
      rendered.thread += 1
    }),
  }
})
vi.mock("@/features/dashboard/right-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/dashboard/right-panel")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    RightPanel: countRenders(actual.RightPanel, () => {
      rendered.rightPanel += 1
    }),
  }
})
vi.mock("@/features/studio/studio-panel", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/studio/studio-panel")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    StudioPanel: countRenders(actual.StudioPanel, () => {
      rendered.studio += 1
    }),
  }
})

const LIST =
  "/workspaces/1/documents?document_type=FILE&document_type=NOTE&limit=200&offset=0"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}
const thread = {
  id: 10,
  workspace_id: 1,
  title: "Streaming chat",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}
const documents = ["a.pdf", "b.pdf", "c.pdf"].map((title, index) => ({
  id: index + 1,
  title,
  document_type: "FILE",
  mime_type: "application/pdf",
  status: "ready",
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}))
const artifacts = [1, 2].map((id) => ({
  id,
  document_id: 100 + id,
  format: "summary",
  generation: 1,
  title: `Artifact ${id}`,
  status: "ready",
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
  version: null,
  spec_kind: null,
  refinable: false,
}))

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem("surfsense:last-thread:1:v1", "10")
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
      if (path === LIST) return Response.json(documents)
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/chat/threads/10/messages") return Response.json([])
      if (path === "/workspaces/1/studio/formats") return Response.json([])
      if (path === "/workspaces/1/artifacts") return Response.json(artifacts)
      if (path === "/workspaces/1/documents/1/original") {
        return new Response(new Uint8Array([37, 80, 68, 70, 45, 49, 46, 55]))
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function renderDashboard() {
  render(
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
  )
  await screen.findByRole("treeitem", { name: "c.pdf" })
  await screen.findByRole("button", { name: "Artifact 2" })
  rendered.documentRows = 0
  rendered.artifactRows = 0
  rendered.studio = 0
  rendered.sidebar = 0
  rendered.thread = 0
  rendered.rightPanel = 0
}

describe("what a dashboard render touches", () => {
  it("renders no source row, artifact row or Studio for a streamed reply", async () => {
    await renderDashboard()

    act(() => {
      beginRun(10, {
        workspaceId: workspace.id,
        pair: [
          {
            id: "optimistic-user-1",
            role: "user",
            content: { text: "q" },
            created_at: null,
            completed_at: null,
          },
          {
            id: "optimistic-assistant-1",
            role: "assistant",
            content: { text: "", citations: [] },
            created_at: null,
            completed_at: null,
          },
        ],
      })
    })
    for (const token of ["Streamed ", "reply ", "text"]) {
      act(() =>
        updatePair(10, ([user, assistant]) => [
          user,
          {
            ...assistant,
            content: {
              ...assistant.content,
              text: `${assistant.content.text ?? ""}${token}`,
            },
          },
        ])
      )
    }

    expect(await screen.findByText("Streamed reply text")).toBeTruthy()
    expect(rendered).toMatchObject({
      documentRows: 0,
      artifactRows: 0,
      studio: 0,
    })
  })

  it("renders nothing inside the columns while a column edge is dragged", async () => {
    await renderDashboard()
    const edge = screen.getByRole("separator", { name: "Resize sidebar" })

    fireEvent.pointerDown(edge, { button: 0, pointerId: 1, clientX: 600 })
    for (const x of [610, 620, 630]) {
      fireEvent.pointerMove(edge, { pointerId: 1, clientX: x })
    }
    fireEvent.pointerUp(edge, { pointerId: 1, clientX: 630 })

    expect(document.getElementById("workspace-left-column")?.style.width).toBe(
      "302px"
    )
    expect(rendered).toEqual({
      documentRows: 0,
      artifactRows: 0,
      studio: 0,
      sidebar: 0,
      thread: 0,
      rightPanel: 0,
    })
  })

  it("renders no source row when a source preview opens", async () => {
    const user = userEvent.setup()
    await renderDashboard()

    await user.click(screen.getByRole("button", { name: "a.pdf" }))

    await screen.findByRole("complementary", { name: "Source preview" })
    expect(rendered.documentRows).toBe(0)
  })
})
