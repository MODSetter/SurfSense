import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { TooltipProvider } from "@/components/ui/tooltip"

import { SourcesAddButton, SourcesPanel } from "../sources-panel"
import { useSources } from "../use-sources"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

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
  source(20, "paper.pdf", 2),
  source(30, "deep.txt", 3),
]

type Call = { path: string; method: string; body: unknown }

/** The folders API as the backend serves it, recording every write. */
function folderApi() {
  let folders = [...FOLDERS]
  let documents = [...DOCUMENTS]
  const writes: Call[] = []
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      const body =
        init?.body instanceof FormData
          ? init.body
          : init?.body
            ? JSON.parse(String(init.body))
            : null
      if (method !== "GET") writes.push({ path, method, body })
      if (path.endsWith("/events")) return new Promise<Response>(() => {})
      if (path === LIST) return Response.json(documents)
      if (path === "/workspaces/1/folders" && method === "GET") {
        return Response.json(folders)
      }
      if (path === "/workspaces/1/folders" && method === "POST") {
        const created = { id: 4, ...(body as { name: string }) }
        folders = [...folders, created as (typeof folders)[number]]
        return Response.json(created, { status: 201 })
      }
      const folderMatch = path.match(/^\/workspaces\/1\/folders\/(\d+)$/)
      if (folderMatch && method === "PATCH") {
        const id = Number(folderMatch[1])
        folders = folders.map((folder) =>
          folder.id === id ? { ...folder, ...(body as object) } : folder
        )
        return Response.json(folders.find((folder) => folder.id === id))
      }
      const summaryMatch = path.match(
        /^\/workspaces\/1\/folders\/(\d+)\/summary$/
      )
      if (summaryMatch) {
        // Research holds paper.pdf and deep.txt, and one filed Studio output
        // the panel never lists.
        return Response.json({ folders: 1, sources: 2, artifacts: 1 })
      }
      if (folderMatch && method === "DELETE") {
        return new Response(null, { status: 204 })
      }
      if (path === "/workspaces/1/documents/move") {
        const { document_ids, folder_id } = body as {
          document_ids: number[]
          folder_id: number
        }
        documents = documents.map((document) =>
          document_ids.includes(document.id)
            ? { ...document, folder_id }
            : document
        )
        return Response.json({ moved: document_ids, skipped: [] })
      }
      if (path === "/workspaces/1/documents/upload") {
        return Response.json(
          { created: [], duplicates: [], rejected: [] },
          { status: 201 }
        )
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return { writes }
}

function TreeHarness() {
  const sources = useSources(1)
  return (
    <TooltipProvider>
      <SourcesPanel
        documents={sources.documents}
        index={sources.index}
        selectedDocumentIds={sources.includedDocumentIds}
        folderTicks={sources.folderTicks}
        highlightedDocumentId={null}
        isLoading={sources.isLoading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        addAction={
          <SourcesAddButton
            isUploading={sources.isUploading}
            onUpload={(files) => void sources.upload(files)}
            onUploadFolder={(entries) => void sources.uploadEntries(entries)}
          />
        }
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={sources.setDocumentIncluded}
        onFolderSelectionChange={sources.setFolderIncluded}
        onToggleAll={sources.toggleAllIncluded}
        onDropFiles={(entries, folderId) =>
          void sources.uploadEntries(entries, folderId)
        }
        folderActions={sources.folderActions}
      />
      <output aria-label="Source scope">
        {JSON.stringify(sources.sourceScope)}
      </output>
    </TooltipProvider>
  )
}

const row = (name: string) => screen.getByRole("treeitem", { name })
const scopeSent = () =>
  JSON.parse(screen.getByLabelText("Source scope").textContent ?? "null")

/** A drag's data, carried from dragstart to drop as a browser would. */
function dragData() {
  const data = new Map<string, string>()
  return {
    get types() {
      return [...data.keys()]
    },
    setData: (type: string, value: string) => data.set(type, value),
    getData: (type: string) => data.get(type) ?? "",
    effectAllowed: "",
    dropEffect: "",
  }
}

/** A folder dropped from the desktop, as Chromium's entry API hands it out. */
function droppedFolder(name: string, files: Record<string, File>) {
  const fileEntry = (path: string, file: File) => ({
    isFile: true,
    isDirectory: false,
    fullPath: `/${name}/${path}`,
    file: (resolve: (file: File) => void) => resolve(file),
  })
  const directory = {
    isFile: false,
    isDirectory: true,
    fullPath: `/${name}`,
    createReader: () => {
      let read = false
      return {
        readEntries: (resolve: (entries: unknown[]) => void) => {
          const page = read
            ? []
            : Object.entries(files).map(([path, file]) => fileEntry(path, file))
          read = true
          resolve(page)
        },
      }
    },
  }
  return {
    types: ["Files"],
    files: [],
    items: [{ kind: "file", webkitGetAsEntry: () => directory }],
  }
}

beforeEach(() => {
  vi.clearAllMocks()
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

describe("source tree", () => {
  it("lists folders before sources and walks them with the arrow keys", async () => {
    folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    const research = await screen.findByRole("treeitem", { name: "Research" })
    expect(screen.getByRole("tree", { name: "Sources" })).toBeTruthy()
    expect(
      screen
        .getAllByRole("treeitem")
        .map((item) => item.getAttribute("aria-label"))
    ).toEqual(["Research", "notes.md"])
    expect(research.getAttribute("aria-expanded")).toBe("false")
    expect(research.getAttribute("aria-level")).toBe("1")

    research.focus()
    await user.keyboard("{ArrowRight}")
    expect(research.getAttribute("aria-expanded")).toBe("true")
    expect(row("paper.pdf").getAttribute("aria-level")).toBe("2")

    await user.keyboard("{ArrowDown}")
    expect(document.activeElement).toBe(row("2024"))
    await user.keyboard("{ArrowLeft}")
    expect(document.activeElement).toBe(research)
    await user.keyboard("{ArrowLeft}")
    expect(research.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("treeitem", { name: "paper.pdf" })).toBeNull()
  })

  it("ticks everything in a folder with Space and sends the folder, not its rows", async () => {
    folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await screen.findByRole("treeitem", { name: "Research" })
    await user.click(screen.getByRole("button", { name: "Deselect all" }))
    row("Research").focus()
    await user.keyboard(" ")

    const folderBox = screen.getByRole("checkbox", {
      name: "Select folder Research",
    })
    expect(folderBox.getAttribute("aria-checked")).toBe("true")
    expect(scopeSent()).toEqual({
      all: false,
      folder_ids: [2],
      excluded_folder_ids: [],
      document_ids: [],
      excluded_document_ids: [],
    })

    await user.keyboard("{ArrowRight}")
    await user.click(screen.getByRole("checkbox", { name: "Select paper.pdf" }))
    expect(folderBox.getAttribute("aria-checked")).toBe("mixed")
    expect(scopeSent()).toMatchObject({
      folder_ids: [2],
      excluded_document_ids: [20],
    })
  })

  it("announces each row's tick on the row a keyboard user is on", async () => {
    folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    const research = await screen.findByRole("treeitem", { name: "Research" })
    expect(research.getAttribute("aria-checked")).toBe("true")
    await user.click(screen.getByRole("button", { name: "Deselect all" }))
    expect(research.getAttribute("aria-checked")).toBe("false")
    research.focus()
    await user.keyboard("{ArrowRight}")
    await user.click(screen.getByRole("checkbox", { name: "Select paper.pdf" }))

    expect(row("paper.pdf").getAttribute("aria-checked")).toBe("true")
    expect(research.getAttribute("aria-checked")).toBe("mixed")
  })

  it("makes a folder at the top of the Library", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await screen.findByRole("treeitem", { name: "Research" })
    await user.click(screen.getByRole("button", { name: "New folder" }))
    const dialog = await screen.findByRole("dialog", { name: "New folder" })
    await user.type(within(dialog).getByLabelText("Name"), "Archive")
    await user.click(within(dialog).getByRole("button", { name: "Create" }))

    expect(
      await screen.findByRole("treeitem", { name: "Archive" })
    ).toBeTruthy()
    expect(writes).toContainEqual({
      path: "/workspaces/1/folders",
      method: "POST",
      body: { parent_id: 1, name: "Archive" },
    })
  })

  it("renames a folder from its menu", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for folder Research" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const dialog = await screen.findByRole("dialog", { name: "Rename folder" })
    const name = within(dialog).getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Papers")
    await user.click(within(dialog).getByRole("button", { name: "Rename" }))

    expect(await screen.findByRole("treeitem", { name: "Papers" })).toBeTruthy()
    expect(writes).toContainEqual({
      path: "/workspaces/1/folders/2",
      method: "PATCH",
      body: { name: "Papers" },
    })
  })

  it("moves a source with the Move to… picker", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for notes.md" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }))
    const dialog = await screen.findByRole("dialog", { name: "Move notes.md" })
    await user.click(within(dialog).getByRole("radio", { name: "Research" }))
    await user.click(within(dialog).getByRole("button", { name: "Move" }))

    await waitFor(() =>
      expect(writes).toContainEqual({
        path: "/workspaces/1/documents/move",
        method: "POST",
        body: { document_ids: [10], folder_id: 2 },
      })
    )
    // The folder it went to opens, showing it there.
    expect(
      (await screen.findByRole("treeitem", { name: "notes.md" })).getAttribute(
        "aria-level"
      )
    ).toBe("2")
  })

  it("keeps a folder from moving inside itself", async () => {
    folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for folder Research" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }))
    const dialog = await screen.findByRole("dialog", { name: "Move Research" })

    expect(
      within(dialog)
        .getAllByRole("radio")
        .map((radio) => radio.closest("label")?.textContent)
    ).toEqual(["Library"])
  })

  it("moves a folder dragged onto another folder", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)
    const research = await screen.findByRole("treeitem", { name: "Research" })
    // A second top-level folder to drag Research into.
    await user.click(screen.getByRole("button", { name: "New folder" }))
    const dialog = await screen.findByRole("dialog", { name: "New folder" })
    await user.type(within(dialog).getByLabelText("Name"), "Archive")
    await user.click(within(dialog).getByRole("button", { name: "Create" }))
    const archive = await screen.findByRole("treeitem", { name: "Archive" })

    const dataTransfer = dragData()
    fireEvent.dragStart(research, { dataTransfer })
    fireEvent.dragOver(archive, { dataTransfer })
    fireEvent.drop(archive, { dataTransfer })

    await waitFor(() =>
      expect(writes).toContainEqual({
        path: "/workspaces/1/folders/2",
        method: "PATCH",
        body: { parent_id: 4 },
      })
    )
  })

  it("names how many sources and filed outputs a folder delete removes", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await user.click(
      await screen.findByRole("button", { name: "Actions for folder Research" })
    )
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }))
    const dialog = await screen.findByRole("alertdialog", {
      name: "Delete Research?",
    })
    expect(dialog.textContent).toContain("the 2 sources in it")
    expect(dialog.textContent).toContain("the 1 Studio output filed in it")
    await user.click(
      within(dialog).getByRole("button", {
        name: "Delete folder and 2 sources",
      })
    )

    await waitFor(() =>
      expect(writes).toContainEqual({
        path: "/workspaces/1/folders/2",
        method: "DELETE",
        body: null,
      })
    )
  })

  it("filters by name and opens the folders holding a match", async () => {
    folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)

    await screen.findByRole("treeitem", { name: "Research" })
    await user.type(
      screen.getByRole("searchbox", { name: "Filter sources by name" }),
      "DEEP"
    )

    expect(
      screen
        .getAllByRole("treeitem")
        .map((item) => item.getAttribute("aria-label"))
    ).toEqual(["Research", "2024", "deep.txt"])
    expect(row("2024").getAttribute("aria-expanded")).toBe("true")

    await user.clear(
      screen.getByRole("searchbox", { name: "Filter sources by name" })
    )
    await user.type(
      screen.getByRole("searchbox", { name: "Filter sources by name" }),
      "nothing like it"
    )
    expect(screen.getByText("No sources match “nothing like it”")).toBeTruthy()
  })

  it("uploads a folder dropped on a folder row into it, with each file's path", async () => {
    const { writes } = folderApi()
    render(<TreeHarness />)
    const research = await screen.findByRole("treeitem", { name: "Research" })
    const a = new File(["a"], "a.md", { type: "text/markdown" })
    const b = new File(["b"], "b.txt", { type: "text/plain" })
    const clutter = new File(["x"], "HEAD")

    fireEvent.drop(research, {
      dataTransfer: droppedFolder("Trip", {
        "a.md": a,
        "sub/b.txt": b,
        ".git/HEAD": clutter,
      }),
    })

    await waitFor(() =>
      expect(
        writes.some((write) => write.path === "/workspaces/1/documents/upload")
      ).toBe(true)
    )
    const sent = writes.find(
      (write) => write.path === "/workspaces/1/documents/upload"
    )?.body as FormData
    expect(sent.getAll("files")).toEqual([a, b])
    expect(sent.get("folder_id")).toBe("2")
    expect(JSON.parse(String(sent.get("relative_paths")))).toEqual([
      "Trip/a.md",
      "Trip/sub/b.txt",
    ])
  })

  it("uploads a picked folder with each file's path", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)
    await screen.findByRole("treeitem", { name: "Research" })
    const a = new File(["a"], "a.md", { type: "text/markdown" })
    Object.defineProperty(a, "webkitRelativePath", { value: "Trip/a.md" })

    const picker = screen.getByLabelText("Upload a source folder")
    expect(picker.hasAttribute("webkitdirectory")).toBe(true)
    await user.upload(picker, a)

    await waitFor(() =>
      expect(
        writes.some((write) => write.path === "/workspaces/1/documents/upload")
      ).toBe(true)
    )
    const sent = writes.find(
      (write) => write.path === "/workspaces/1/documents/upload"
    )?.body as FormData
    expect(sent.get("folder_id")).toBeNull()
    expect(JSON.parse(String(sent.get("relative_paths")))).toEqual([
      "Trip/a.md",
    ])
  })

  it("sets aside a file over 500 MB and uploads the rest", async () => {
    const { writes } = folderApi()
    const user = userEvent.setup()
    render(<TreeHarness />)
    await screen.findByRole("treeitem", { name: "Research" })
    const small = new File(["a"], "small.md", { type: "text/markdown" })
    const huge = new File(["b"], "huge.pdf", { type: "application/pdf" })
    Object.defineProperty(huge, "size", { value: 501 * 1024 * 1024 })

    await user.upload(screen.getByLabelText("Upload source files"), [
      small,
      huge,
    ])

    await waitFor(() =>
      expect(toast.info).toHaveBeenCalledWith(
        "No new sources added",
        expect.objectContaining({
          description: "Rejected: huge.pdf (Over 500 MB)",
        })
      )
    )
    const sent = writes.find(
      (write) => write.path === "/workspaces/1/documents/upload"
    )?.body as FormData
    expect(sent.getAll("files")).toEqual([small])
  })
})
