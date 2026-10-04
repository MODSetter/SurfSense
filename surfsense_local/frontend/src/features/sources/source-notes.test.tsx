import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { toast } from "sonner"

import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { SourcesPanel } from "./sources-panel"
import { useSources } from "./use-sources"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const LIST = "/workspaces/1/documents?document_type=FILE&document_type=NOTE"

const file = {
  id: 7,
  title: "guide.txt",
  document_type: "FILE" as const,
  mime_type: "text/plain",
  status: "ready" as const,
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

const note = {
  ...file,
  id: 8,
  title: "Ideas",
  document_type: "NOTE" as const,
  mime_type: null,
}

function NotesHarness() {
  const sources = useSources(1)
  return (
    <TooltipProvider>
      <SourcesPanel
        documents={sources.documents}
        selectedDocumentIds={sources.includedDocumentIds}
        highlightedDocumentId={null}
        isLoading={sources.isLoading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={sources.setDocumentIncluded}
        onToggleAll={sources.toggleAllIncluded}
        onRename={sources.rename}
        notes={{
          write: sources.writeNote,
          load: sources.loadNote,
          edit: sources.editNote,
        }}
      />
    </TooltipProvider>
  )
}

/** The workspace's documents, and every write the panel sends. */
function serving(documents: object[], { failWrites = false } = {}) {
  const writes: { method: string; path: string; body: unknown }[] = []
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (method === "GET" && path === LIST) return Response.json(documents)
      if (method === "GET" && path === "/workspaces/1/documents/8") {
        return Response.json({
          ...note,
          content: "First draft",
          document_metadata: null,
        })
      }
      if (method === "GET") return Response.json([])
      const body = init?.body ? JSON.parse(String(init.body)) : null
      writes.push({ method, path, body })
      if (failWrites) {
        return Response.json({ detail: "database is locked" }, { status: 503 })
      }
      if (method === "POST" && path === "/workspaces/1/documents") {
        return Response.json(
          {
            ...note,
            id: 9,
            ...body,
            status: "pending",
            document_metadata: null,
          },
          { status: 201 }
        )
      }
      if (method === "PATCH") {
        const id = Number(path.split("/").pop())
        const current = documents.find((d) => (d as { id: number }).id === id)
        return Response.json({
          ...current,
          ...body,
          content: null,
          document_metadata: null,
        })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return writes
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
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("notes and renaming in the sources panel", () => {
  it("writes a note that then appears in the list", async () => {
    const writes = serving([file])
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(await screen.findByRole("button", { name: "New note" }))
    await user.type(
      await screen.findByRole("textbox", { name: "Title" }),
      "Plan"
    )
    await user.type(screen.getByRole("textbox", { name: "Note" }), "Ship it")
    await user.click(screen.getByRole("button", { name: "Save note" }))

    await waitFor(() => expect(screen.getByText("Plan")).toBeTruthy())
    expect(writes).toEqual([
      {
        method: "POST",
        path: "/workspaces/1/documents",
        body: { title: "Plan", content: "Ship it" },
      },
    ])
  })

  it("renames a file without sending any content", async () => {
    // PATCH answers 409 for content on anything but a note.
    const writes = serving([file])
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for guide.txt" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const name = await screen.findByRole("textbox", { name: "Name" })
    await user.clear(name)
    await user.type(name, "Field guide")
    await user.click(screen.getByRole("button", { name: "Rename" }))

    await waitFor(() => expect(screen.getByText("Field guide")).toBeTruthy())
    expect(writes).toEqual([
      {
        method: "PATCH",
        path: "/workspaces/1/documents/7",
        body: { title: "Field guide" },
      },
    ])
  })

  it("reopens a note with its text and saves the edit", async () => {
    const writes = serving([note])
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for Ideas" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Edit note" }))
    const body = await screen.findByRole("textbox", { name: "Note" })
    await waitFor(() =>
      expect((body as HTMLTextAreaElement).value).toBe("First draft")
    )
    await user.type(body, ", revised")
    await user.click(screen.getByRole("button", { name: "Save note" }))

    await waitFor(() =>
      expect(writes).toEqual([
        {
          method: "PATCH",
          path: "/workspaces/1/documents/8",
          body: { title: "Ideas", content: "First draft, revised" },
        },
      ])
    )
  })

  it("refuses a name of spaces before sending anything", async () => {
    const writes = serving([file])
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for guide.txt" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const name = await screen.findByRole("textbox", { name: "Name" })
    await user.clear(name)
    await user.type(name, "   ")

    expect(
      (screen.getByRole("button", { name: "Rename" }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
    expect(writes).toEqual([])
  })

  it("sends no content when only a note's title changed", async () => {
    // Content puts the note back to pending and re-ingests it for nothing.
    const writes = serving([note])
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for Ideas" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Edit note" }))
    const body = await screen.findByRole("textbox", { name: "Note" })
    await waitFor(() =>
      expect((body as HTMLTextAreaElement).value).toBe("First draft")
    )
    const title = screen.getByRole("textbox", { name: "Title" })
    await user.clear(title)
    await user.type(title, "Plans")
    await user.click(screen.getByRole("button", { name: "Save note" }))

    await waitFor(() =>
      expect(writes).toEqual([
        {
          method: "PATCH",
          path: "/workspaces/1/documents/8",
          body: { title: "Plans" },
        },
      ])
    )
  })

  it("says why a rename failed where it can be seen, and keeps the dialog", async () => {
    // The panel's own alert sits behind the dialog's backdrop.
    serving([file], { failWrites: true })
    const user = userEvent.setup()
    render(<NotesHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for guide.txt" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const name = await screen.findByRole("textbox", { name: "Name" })
    await user.clear(name)
    await user.type(name, "Field guide")
    await user.click(screen.getByRole("button", { name: "Rename" }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Couldn’t rename the source",
        expect.anything()
      )
    )
    expect(screen.getByRole("textbox", { name: "Name" })).toBeTruthy()
  })
})
