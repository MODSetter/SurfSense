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
      selectedDocument={null}
      selectedCitation={null}
      isLoading={sources.isLoading}
      isLoadingPreview={false}
      isUploading={sources.isUploading}
      isDeleting={sources.isDeleting}
      error={sources.error}
      onOpen={() => undefined}
      onBack={() => undefined}
      onRetry={(id) => void sources.retry(id)}
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
        selectedDocument={null}
        selectedCitation={null}
        isLoading={false}
        isLoadingPreview={false}
        isUploading={false}
        isDeleting={false}
        error={null}
        onOpen={vi.fn()}
        onBack={vi.fn()}
        onRetry={vi.fn()}
        onDeleteSelected={vi.fn()}
        onSelectionChange={vi.fn()}
        onUpload={vi.fn()}
      />
    )

    expect(screen.getByLabelText(`Select ${ready.title}`)).toBeTruthy()
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
    const readyButton = screen.getByRole("button", { name: ready.title })
    expect(readyButton.className).toContain("truncate")
    expect(readyButton.parentElement?.className).toContain("overflow-hidden")
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
    await user.upload(screen.getByLabelText("Upload source files"), file)

    expect(await screen.findByText("guide.txt")).toBeTruthy()
    expect(
      await screen.findByRole("status", { name: "Processing guide.txt" })
    ).toBeTruthy()
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("1 source added", {
        id: "source-upload-outcome",
        description:
          "Ingestion is running in the background. Already present: copy.txt",
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

  it("shows upload failures in a toast instead of the sources panel", async () => {
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
    const user = userEvent.setup()

    render(<SourceHarness />)
    await screen.findByText("No sources yet")
    await user.upload(
      screen.getByLabelText("Upload source files"),
      new File(["content"], "unsupported.exe")
    )

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Couldn’t add your source", {
        id: "source-upload-error",
        description: "Unsupported file type",
      })
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
    await user.click(await screen.findByLabelText("Select first.txt"))
    await user.click(screen.getByLabelText("Select second.txt"))
    await user.click(screen.getByRole("button", { name: "Delete 2" }))

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
