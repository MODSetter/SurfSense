import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { SourcePreviewPanel } from "./source-preview-panel"

const NOTE = {
  id: 5,
  title: "paper.pdf",
  document_type: "FILE" as const,
  mime_type: "application/pdf",
  status: "ready" as const,
  error_message: null,
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
  folder_id: 1,
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the source preview in the Docker image", { tags: ["docker"] }, () => {
  it("offers the file as a download, since no app here can open it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array(), { status: 200 }))
    )
    const onOpen = vi.fn()
    const user = userEvent.setup()
    render(
      <SourcePreviewPanel
        workspaceId={1}
        document={NOTE}
        onOpen={onOpen}
        onClose={vi.fn()}
      />
    )

    await user.click(screen.getByRole("button", { name: "Download file" }))

    expect(onOpen).toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "Open file" })).toBeNull()
  })
})
