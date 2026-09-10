import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ArtifactList } from "./artifact-list"
import type { Artifact } from "./api"

const artifact: Artifact = {
  id: 12,
  document_id: 4,
  format: "summary",
  generation: 1,
  title: "Weekly summary",
  status: "ready",
  error_message: null,
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
}

afterEach(cleanup)

describe("artifact list", () => {
  it("shows an empty state", () => {
    render(
      <ArtifactList
        artifacts={[]}
        labelOf={(format) => format}
        onOpen={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    expect(screen.getByText("No generated artifacts yet")).toBeTruthy()
  })

  it("opens ready artifacts", async () => {
    const onOpen = vi.fn()
    const user = userEvent.setup()
    render(
      <ArtifactList
        artifacts={[artifact]}
        labelOf={() => "Summary"}
        onOpen={onOpen}
        onDelete={vi.fn()}
      />
    )

    expect(
      screen.getByRole("heading", { name: "All generated artifacts" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: /^Weekly summary/ }))
    expect(onOpen).toHaveBeenCalledWith(12)
  })

  it("shows the stored failure reason without opening the artifact", async () => {
    const onOpen = vi.fn()
    const user = userEvent.setup()
    render(
      <ArtifactList
        artifacts={[
          {
            ...artifact,
            id: 13,
            title: "Flashcards",
            status: "failed",
            error_message: "ConnectError: All connection attempts failed",
          },
        ]}
        labelOf={() => "Flashcards"}
        onOpen={onOpen}
        onDelete={vi.fn()}
      />
    )

    expect(screen.getByText("failed")).toBeTruthy()
    expect(
      screen.getByText("ConnectError: All connection attempts failed")
    ).toBeTruthy()
    const failed = screen.getByRole("button", {
      name: /^Flashcards/,
    })
    expect((failed as HTMLButtonElement).disabled).toBe(true)
    await user.click(failed)
    expect(onOpen).not.toHaveBeenCalled()
  })
})
