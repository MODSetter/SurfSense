import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { SourcesPanel } from "./sources-panel"
import { useSources } from "./use-sources"

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}))

const pendingDocument = {
  id: 7,
  title: "guide.txt",
  document_type: "FILE" as const,
  status: "pending" as const,
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

function SourceHarness() {
  const sources = useSources(1)
  return (
    <SourcesPanel
      documents={sources.documents}
      selectedDocumentIds={sources.selectedDocumentIds}
      highlightedDocumentId={null}
      isLoading={sources.isLoading}
      isUploading={sources.isUploading}
      isDeleting={sources.isDeleting}
      error={sources.error}
      onOpen={(id) => void sources.openOriginal(id)}
      onReveal={(id) => void sources.revealOriginal(id)}
      onRetry={(id) => void sources.retry(id)}
      onDelete={(id) => void sources.deleteOne(id)}
      onDeleteSelected={() => void sources.deleteSelected()}
      onSelectionChange={sources.setDocumentSelected}
      onUpload={(files) => void sources.upload(files)}
    />
  )
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
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("source upload", () => {
  it("uses selection, processing, and retry controls in the icon slot", () => {
    const ready = {
      ...pendingDocument,
      id: 1,
      title:
        "A very long ready source name that must stay inside the panel.pdf",
      status: "ready" as const,
    }
    const processing = {
      ...pendingDocument,
      id: 2,
      title: "processing.pdf",
      status: "processing" as const,
    }
    const failed = {
      ...pendingDocument,
      id: 3,
      title: "failed.pdf",
      status: "failed" as const,
    }

    render(
      <SourcesPanel
        documents={[ready, processing, failed]}
        selectedDocumentIds={[]}
        highlightedDocumentId={ready.id}
        isLoading={false}
        isUploading={false}
        isDeleting={false}
        error={null}
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onDelete={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={vi.fn()}
        onUpload={vi.fn()}
      />
    )

    const readyCheckbox = screen.getByLabelText(`Select ${ready.title}`)
    expect(readyCheckbox).toBeTruthy()
    expect(screen.queryByLabelText("Select processing.pdf")).toBeNull()
    expect(screen.queryByLabelText("Select failed.pdf")).toBeNull()
    expect(
      screen.getByRole("status", { name: "Processing processing.pdf" })
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Retry failed.pdf" })
    ).toBeTruthy()
    expect(
      screen.getAllByRole("button", { name: /^Actions for / })
    ).toHaveLength(3)
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "nearest",
    })
    const readyButton = screen.getByRole("button", { name: ready.title })
    const actionsButton = screen.getByRole("button", {
      name: `Actions for ${ready.title}`,
    })
    expect(readyButton.className).not.toContain("truncate")
    expect(readyButton.className).toContain("sidebar-row-title-fade")
    expect(readyButton.parentElement?.className).toContain("overflow-hidden")
    expect(readyButton.parentElement?.className).toContain("h-8")
    expect(readyButton.parentElement?.className).toContain("gap-1.5")
    expect(readyButton.parentElement?.className).toContain("pl-1")
    expect(readyButton.parentElement?.className).toContain("rounded-lg")
    expect(readyButton.parentElement?.className).toContain("hover:bg-muted")
    expect(readyButton.parentElement?.className).toContain(
      "dark:hover:bg-muted/50"
    )
    expect(readyButton.parentElement?.className).toContain("border-ring")
    expect(readyButton.parentElement?.className).not.toContain(
      "bg-sidebar-accent"
    )
    expect(readyButton.parentElement?.className).not.toContain("text-white")
    expect(readyButton.parentElement?.getAttribute("aria-current")).toBe("true")
    expect(
      readyButton.previousElementSibling
        ?.querySelector("svg")
        ?.getAttribute("class")
    ).toContain("size-4.5")
    expect(readyCheckbox.className).not.toContain(
      "group-focus-within/source:opacity-100"
    )
    expect(readyCheckbox.className).toContain("focus-visible:opacity-100")
    expect(readyCheckbox.nextElementSibling?.className).toContain(
      "peer-focus-visible:opacity-0"
    )
    expect(actionsButton.className).toContain("size-6")
    expect(actionsButton.className).toContain("group-hover/source:opacity-100")
    expect(actionsButton.className).not.toContain(
      "group-focus-within/source:opacity-100"
    )
    expect(actionsButton.className).toContain("focus-visible:opacity-100")
    expect(
      screen.getByRole("heading", { name: "Sources" }).parentElement?.className
    ).toContain("px-3")
    expect(
      screen.getByRole("heading", { name: "All sources" }).closest("section")
        ?.parentElement?.className
    ).toContain("p-2")
  })

  it("offers per-source delete but disables it while processing", async () => {
    const onDelete = vi.fn()
    const user = userEvent.setup()

    render(
      <SourcesPanel
        documents={[
          pendingDocument,
          {
            ...pendingDocument,
            id: 2,
            title: "processing.pdf",
            status: "processing",
          },
        ]}
        selectedDocumentIds={[]}
        highlightedDocumentId={null}
        isLoading={false}
        isUploading={false}
        isDeleting={false}
        error={null}
        onOpen={vi.fn()}
        onReveal={vi.fn()}
        onRetry={vi.fn()}
        onDelete={onDelete}
        onDeleteSelected={vi.fn()}
        onSelectionChange={vi.fn()}
        onUpload={vi.fn()}
      />
    )

    await user.click(
      screen.getByRole("button", { name: "Actions for processing.pdf" })
    )
    expect(
      screen
        .getByRole("menuitem", { name: "Delete" })
        .getAttribute("data-disabled")
    ).not.toBeNull()
    await user.keyboard("{Escape}")

    await user.click(
      screen.getByRole("button", { name: "Actions for guide.txt" })
    )
    expect(
      screen
        .getByRole("menuitem", { name: "Delete" })
        .getAttribute("data-disabled")
    ).toBeNull()
    await user.click(screen.getByRole("menuitem", { name: "Delete" }))
    await user.click(screen.getByRole("button", { name: "Delete source" }))

    expect(onDelete).toHaveBeenCalledWith(pendingDocument.id)
  })

  it("permanently deletes one failed source after confirmation", async () => {
    const failedDocument = {
      ...pendingDocument,
      title: "broken.pdf",
      status: "failed" as const,
    }
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === "DELETE"
          ? new Response(null, { status: 204 })
          : Response.json([failedDocument])
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<SourceHarness />)
    await user.click(
      await screen.findByRole("button", { name: "Actions for broken.pdf" })
    )
    await user.click(screen.getByRole("menuitem", { name: "Delete" }))
    expect(
      screen.getByRole("alertdialog", { name: "Delete 1 source?" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete source" }))

    await waitFor(() => expect(screen.queryByText("broken.pdf")).toBeNull())
    expect(fetchMock).toHaveBeenCalledWith(
      "/workspaces/1/documents/7",
      expect.objectContaining({ method: "DELETE" })
    )
  })

  it("uploads multipart files, reports duplicates, and polls until ready", async () => {
    let uploaded = false
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (
          path ===
            "/workspaces/1/documents?document_type=FILE&document_type=NOTE" &&
          !uploaded
        ) {
          return Response.json([])
        }
        if (
          path === "/workspaces/1/documents/upload" &&
          init?.method === "POST"
        ) {
          uploaded = true
          return Response.json(
            {
              created: [pendingDocument],
              duplicates: [{ filename: "copy.txt", document_id: 7 }],
              rejected: [
                {
                  filename: "broken.pdf",
                  reason: "file contents do not match .pdf",
                },
              ],
            },
            { status: 201 }
          )
        }
        if (
          path ===
          "/workspaces/1/documents?document_type=FILE&document_type=NOTE"
        ) {
          return Response.json([{ ...pendingDocument, status: "ready" }])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<SourceHarness />)
    await screen.findByText("No sources yet")

    const file = new File(["local research"], "guide.txt", {
      type: "text/plain",
    })
    const input = screen.getByLabelText("Upload source files")
    expect(input.getAttribute("accept")).toContain(".pdf")
    expect(input.getAttribute("accept")).toContain(".webp")
    await user.upload(input, file)

    expect(await screen.findByText("guide.txt")).toBeTruthy()
    expect(
      await screen.findByRole("status", { name: "Processing guide.txt" })
    ).toBeTruthy()
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("1 source added", {
        id: "source-upload-outcome",
        description:
          "Ingestion is running in the background. Already present: copy.txt " +
          "Rejected: broken.pdf (file contents do not match .pdf)",
      })
    )

    const uploadCall = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/workspaces/1/documents/upload" && init?.method === "POST"
    )
    const body = uploadCall?.[1]?.body
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get("files")).toBe(file)
    expect(new Headers(uploadCall?.[1]?.headers).has("Content-Type")).toBe(
      false
    )

    await waitFor(
      () => expect(screen.getByLabelText("Select guide.txt")).toBeTruthy(),
      { timeout: 3000 }
    )
  })

  it("rejects unsupported selections before uploading", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          return Response.json(
            { detail: "Unsupported file type" },
            { status: 400 }
          )
        }
        return Response.json([])
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup({ applyAccept: false })

    render(<SourceHarness />)
    await screen.findByText("No sources yet")
    await user.upload(
      screen.getByLabelText("Upload source files"),
      new File(["content"], "unsupported.exe")
    )

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Couldn’t add your source", {
        id: "source-upload-error",
        description: "Unsupported file type: unsupported.exe",
      })
    )
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/workspaces/1/documents/upload",
      expect.anything()
    )
    expect(screen.queryByText("Source action failed")).toBeNull()
  })

  it("deletes every selected source after confirmation", async () => {
    const documents = [
      {
        ...pendingDocument,
        id: 7,
        title: "first.txt",
        status: "ready" as const,
      },
      {
        ...pendingDocument,
        id: 8,
        title: "second.txt",
        status: "ready" as const,
      },
    ]
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "DELETE") {
          return new Response(null, { status: 204 })
        }
        return Response.json(documents)
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<SourceHarness />)
    const firstCheckbox = await screen.findByLabelText("Select first.txt")
    await user.click(firstCheckbox)
    const firstRow = screen.getByRole("button", {
      name: "first.txt",
    }).parentElement
    expect(firstRow?.className).toContain("bg-sidebar-accent")
    expect(firstRow?.className).toContain("text-white")

    await user.click(firstCheckbox)
    expect(firstRow?.className).not.toContain("bg-sidebar-accent")
    expect(firstRow?.className).not.toContain("text-white")

    await user.click(firstCheckbox)
    await user.click(screen.getByLabelText("Select second.txt"))
    await user.click(screen.getByRole("button", { name: "Delete (2)" }))

    expect(
      screen.getByRole("alertdialog", { name: "Delete 2 sources?" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete sources" }))

    await waitFor(() => {
      expect(screen.queryByText("first.txt")).toBeNull()
      expect(screen.queryByText("second.txt")).toBeNull()
    })
    expect(
      fetchMock.mock.calls
        .filter(([, init]) => init?.method === "DELETE")
        .map(([path]) => path)
    ).toEqual(["/workspaces/1/documents/7", "/workspaces/1/documents/8"])
  })
})
