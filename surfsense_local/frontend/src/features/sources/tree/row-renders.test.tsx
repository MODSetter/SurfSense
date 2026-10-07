import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"

import { SourcesPanel } from "../sources-panel"
import { useSources } from "../use-sources"

// The rows each render that came from the tree, not from their own state.
const rendered = vi.hoisted(() => ({
  documents: [] as number[],
  folders: [] as number[],
}))

vi.mock("./document-row", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./document-row")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    DocumentRow: countRenders(actual.DocumentRow, ({ document }) =>
      rendered.documents.push(document.id)
    ),
  }
})
vi.mock("./folder-row", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./folder-row")>()
  const { countRenders } = await import("@/test-render-count")
  return {
    ...actual,
    FolderRow: countRenders(actual.FolderRow, ({ folder }) =>
      rendered.folders.push(folder.id)
    ),
  }
})

const LIST =
  "/workspaces/1/documents?document_type=FILE&document_type=NOTE&limit=200&offset=0"

function source(id: number, title: string, folderId: number) {
  return {
    id,
    title,
    document_type: "FILE" as const,
    mime_type: null,
    status: "ready" as const,
    error_message: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    folder_id: folderId,
  }
}

// The Library (1) holds Research (2), which holds 2024 (3).
const FOLDERS = [
  { id: 1, parent_id: null, name: "Library" },
  { id: 2, parent_id: 1, name: "Research" },
  { id: 3, parent_id: 2, name: "2024" },
]
const DOCUMENTS = [
  source(10, "notes.md", 1),
  source(11, "plan.md", 1),
  source(20, "paper.pdf", 2),
  source(30, "deep.txt", 3),
]

function Harness() {
  const sources = useSources(1)
  const [, setRenders] = useState(0)
  return (
    <TooltipProvider>
      <button type="button" onClick={() => setRenders((count) => count + 1)}>
        Render again
      </button>
      <SourcesPanel
        documents={sources.documents}
        index={sources.index}
        selectedDocumentIds={sources.includedDocumentIds}
        folderTicks={sources.folderTicks}
        highlightedDocumentId={null}
        isLoading={sources.isLoading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        onOpen={sources.openOriginal}
        onReveal={sources.revealOriginal}
        onRetry={sources.retry}
        onCancel={sources.cancel}
        onDelete={sources.deleteOne}
        onDeleteSelected={sources.deleteSelected}
        onSelectionChange={sources.setDocumentIncluded}
        onFolderSelectionChange={sources.setFolderIncluded}
        onToggleAll={sources.toggleAllIncluded}
        onRename={sources.rename}
        folderActions={sources.folderActions}
      />
    </TooltipProvider>
  )
}

// What the API lists now, and the workspace's event stream, fed by the test.
let listing = DOCUMENTS
let feed: ReadableStreamDefaultController<Uint8Array> | null = null
const encoder = new TextEncoder()
const send = (text: string) => feed?.enqueue(encoder.encode(text))

beforeEach(() => {
  listing = DOCUMENTS
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path.endsWith("/events")) {
        return new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              feed = controller
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } }
        )
      }
      if (path === LIST) return Response.json(listing)
      if (path === "/workspaces/1/folders") return Response.json(FOLDERS)
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function openTree() {
  const user = userEvent.setup()
  render(<Harness />)
  await screen.findByRole("treeitem", { name: "Research" })
  await user.click(screen.getByRole("button", { name: "Expand Research" }))
  await user.click(await screen.findByRole("button", { name: "Expand 2024" }))
  await screen.findByRole("treeitem", { name: "deep.txt" })
  rendered.documents.length = 0
  rendered.folders.length = 0
  return user
}

describe("source tree renders", () => {
  it("renders no row again when the page around it renders", async () => {
    const user = await openTree()

    await user.click(screen.getByRole("button", { name: "Render again" }))

    expect(rendered.documents).toEqual([])
    expect(rendered.folders).toEqual([])
  })

  it("renders only the ticked source and the folders whose tick changes", async () => {
    await openTree()

    fireEvent.click(screen.getByRole("checkbox", { name: "Select deep.txt" }))

    expect(screen.getByRole("treeitem", { name: "deep.txt" }).ariaChecked).toBe(
      "false"
    )
    expect(rendered.documents).toEqual([30])
    // 2024 empties and Research turns mixed; nothing else changed.
    expect(rendered.folders.sort()).toEqual([2, 3])
  })

  it("renders only the two rows the focus moves between", async () => {
    const user = await openTree()
    act(() => screen.getByRole("treeitem", { name: "Research" }).focus())
    rendered.documents.length = 0
    rendered.folders.length = 0

    await user.keyboard("{ArrowDown}")

    expect(document.activeElement).toBe(
      screen.getByRole("treeitem", { name: "2024" })
    )
    expect(rendered.folders.sort()).toEqual([2, 3])
    expect(rendered.documents).toEqual([])
  })

  it("renders only the source a re-read of the list changed", async () => {
    await openTree()
    send(": connected\n\n")
    listing = DOCUMENTS.map((document) =>
      document.id === 20 ? { ...document, title: "paper v2.pdf" } : document
    )

    send(`event: documents\ndata: ${JSON.stringify({ ids: [20] })}\n\n`)

    await screen.findByRole("treeitem", { name: "paper v2.pdf" })
    expect(rendered.documents).toEqual([20])
    expect(rendered.folders).toEqual([])
  })
})
