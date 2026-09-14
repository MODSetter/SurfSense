import { cleanup, render, screen, waitFor } from "@testing-library/react"
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
        onDelete={vi.fn()}
        onRetry={vi.fn()}
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

  it("disables opening a failed artifact and offers a generic retry hint on hover", async () => {
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
    const retryIcon = screen.getByLabelText(
      "Generation failed. Retry Flashcards"
    )
    await user.hover(retryIcon)
    // The real error is reserved for Ctrl/Cmd+hover — see the test below.
    expect(
      await screen.findByRole("tooltip", {
        name: "Generation failed. Retry again.",
      })
    ).toBeTruthy()
    expect(
      screen.queryByRole("tooltip", {
        name: "ConnectError: All connection attempts failed",
      })
    ).toBeNull()
    const failed = screen.getByRole("button", { name: "Flashcards" })
    expect((failed as HTMLButtonElement).disabled).toBe(true)
    await user.click(failed)
    expect(onOpen).not.toHaveBeenCalled()
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

  it("retries a failed artifact from the icon and from the dropdown", async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    renderList({
      artifacts: [{ ...artifact, status: "failed", error_message: "boom" }],
      onRetry,
    })

    await user.click(
      screen.getByLabelText("Generation failed. Retry Weekly summary")
    )
    expect(onRetry).toHaveBeenCalledExactlyOnceWith(12)

    await user.click(
      screen.getByRole("button", { name: "Actions for Weekly summary" })
    )
    expect(screen.queryByRole("menuitem", { name: "Open" })).toBeNull()
    await user.click(screen.getByRole("menuitem", { name: "Retry" }))
    expect(onRetry).toHaveBeenCalledTimes(2)
  })

  it("shows a generic retry hint on plain hover of just the icon", async () => {
    const user = userEvent.setup()
    renderList({
      artifacts: [{ ...artifact, status: "failed", error_message: "boom" }],
    })

    const retryIcon = screen.getByLabelText(
      "Generation failed. Retry Weekly summary"
    )
    await user.hover(retryIcon)
    const generic = await screen.findByRole("tooltip", {
      name: "Generation failed. Retry again.",
    })
    expect(generic.getAttribute("data-side")).toBe("left")
  })

  it("reveals the real error above the whole row while Ctrl/Cmd is held", async () => {
    const user = userEvent.setup()
    renderList({
      artifacts: [{ ...artifact, status: "failed", error_message: "boom" }],
    })

    // Hovering the title, not the icon, proves this covers the whole row.
    const title = screen.getByRole("button", { name: "Weekly summary" })
    await user.hover(title)
    expect(screen.queryByRole("tooltip", { name: "boom" })).toBeNull()

    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Control", ctrlKey: true })
    )
    const real = await screen.findByRole("tooltip", { name: "boom" })
    expect(real.getAttribute("data-side")).toBe("top")

    window.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Control", ctrlKey: false })
    )
    // Radix keeps the node mounted with data-state="closed" through its exit
    // animation, which jsdom never finishes — so wait for it to go rather
    // than asserting synchronously.
    await waitFor(() =>
      expect(screen.queryByRole("tooltip", { name: "boom" })).toBeNull()
    )
  })
})
