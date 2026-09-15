import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"

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

function renderList(props: Partial<Parameters<typeof ArtifactList>[0]> = {}) {
  return render(
    <TooltipProvider>
      <ArtifactList
        artifacts={[artifact]}
        onOpen={vi.fn()}
        onRegenerate={vi.fn()}
        onDelete={vi.fn()}
        {...props}
      />
    </TooltipProvider>
  )
}

afterEach(cleanup)

describe("artifact list", () => {
  it("shows an empty state", () => {
    renderList({ artifacts: [] })

    expect(screen.getByText("No generated artifacts yet")).toBeTruthy()
  })

  it("shows list skeletons while artifacts load", () => {
    renderList({ artifacts: [], isLoading: true })

    expect(screen.queryByText("No generated artifacts yet")).toBeNull()
    expect(
      document.querySelectorAll("[data-slot=skeleton]").length
    ).toBeGreaterThan(0)
  })

  it("dates every row, so two artifacts with one title are told apart", () => {
    const twin = { ...artifact, id: 13, created_at: "2026-09-07T00:00:00Z" }
    renderList({ artifacts: [artifact, twin] })

    const times = document.querySelectorAll("time")
    expect([...times].map((t) => t.getAttribute("datetime"))).toEqual([
      "2026-09-06T00:00:00.000Z",
      "2026-09-07T00:00:00.000Z",
    ])
  })

  it("opens ready artifacts", async () => {
    const onOpen = vi.fn()
    const user = userEvent.setup()
    renderList({ onOpen })

    expect(
      screen.getByRole("heading", { name: "All generated artifacts" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Weekly summary" }))
    expect(onOpen).toHaveBeenCalledWith(12)
  })

  it("shows a spinner while an artifact is generating", () => {
    renderList({
      artifacts: [{ ...artifact, status: "pending" }],
    })

    expect(
      screen.getByRole("status", { name: "Processing Weekly summary" })
    ).toBeTruthy()
    expect(
      (
        screen.getByRole("button", {
          name: "Weekly summary",
        }) as HTMLButtonElement
      ).disabled
    ).toBe(true)
  })

  it("shows the stored failure reason without opening the artifact", async () => {
    const onOpen = vi.fn()
    const user = userEvent.setup()
    renderList({
      artifacts: [
        {
          ...artifact,
          id: 13,
          title: "Flashcards",
          status: "failed",
          error_message: "ConnectError: All connection attempts failed",
        },
      ],
      onOpen,
    })

    expect(screen.queryByText("failed")).toBeNull()
    expect(
      screen.getByLabelText("ConnectError: All connection attempts failed")
    ).toBeTruthy()
    const failed = screen.getByRole("button", { name: "Flashcards" })
    expect((failed as HTMLButtonElement).disabled).toBe(true)
    await user.click(failed)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it("regenerates a failed artifact from the overflow menu", async () => {
    const onRegenerate = vi.fn()
    const user = userEvent.setup()
    renderList({
      artifacts: [
        { ...artifact, status: "failed", error_message: "the model refused" },
      ],
      onRegenerate,
    })

    await user.click(
      screen.getByRole("button", { name: "Actions for Weekly summary" })
    )
    await user.click(screen.getByRole("menuitem", { name: "Regenerate" }))
    expect(onRegenerate).toHaveBeenCalledWith(12)
  })

  it("offers no regenerate while an artifact is generating", async () => {
    const user = userEvent.setup()
    renderList({ artifacts: [{ ...artifact, status: "processing" }] })

    await user.click(
      screen.getByRole("button", { name: "Actions for Weekly summary" })
    )
    expect(screen.queryByRole("menuitem", { name: "Regenerate" })).toBeNull()
  })

  it("deletes from the overflow menu after confirm", async () => {
    const onDelete = vi.fn()
    const user = userEvent.setup()
    renderList({ onDelete })

    await user.click(
      screen.getByRole("button", { name: "Actions for Weekly summary" })
    )
    await user.click(screen.getByRole("menuitem", { name: "Delete" }))
    expect(onDelete).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "Delete artifact" }))
    expect(onDelete).toHaveBeenCalledWith(12)
  })
})
