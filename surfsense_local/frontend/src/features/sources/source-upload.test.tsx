import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { SourcesPanel } from "./sources-panel"
import { useSources } from "./use-sources"

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
      citations={[]}
      selectedDocumentIds={sources.selectedDocumentIds}
      selectedDocument={null}
      selectedCitation={null}
      isLoading={sources.isLoading}
      isLoadingPreview={false}
      isUploading={sources.isUploading}
      isDeleting={sources.isDeleting}
      uploadOutcome={sources.uploadOutcome}
      error={sources.error}
      onOpen={() => undefined}
      onBack={() => undefined}
      onRetry={(id) => void sources.retry(id)}
      onDeleteSelected={() => void sources.deleteSelected()}
      onSelectionChange={sources.setDocumentSelected}
      onUpload={(files) => void sources.upload(files)}
      onDismissUploadOutcome={sources.dismissUploadOutcome}
    />
  )
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
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("source upload", () => {
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
    expect(await screen.findByText("pending")).toBeTruthy()
    expect(await screen.findByText(/Already present: copy\.txt/)).toBeTruthy()

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

    await waitFor(() => expect(screen.getByText("ready")).toBeTruthy(), {
      timeout: 3000,
    })
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
