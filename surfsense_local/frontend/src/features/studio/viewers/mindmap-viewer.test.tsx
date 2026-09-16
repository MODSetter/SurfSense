import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

// The drawing needs real SVG layout, which jsdom lacks; the outline → tree
// step and the controls are what this test covers.
const markmap = {
  setData: vi.fn(),
  fit: vi.fn(),
  destroy: vi.fn(),
  setOptions: vi.fn(),
}
vi.mock("markmap-view", () => ({
  Markmap: { create: () => markmap },
}))

import { MindmapViewer } from "./mindmap-viewer"

const outline = ["# Saturn", "- Rings", "  - Made of ice", "- Moons"].join("\n")

afterEach(() => {
  cleanup()
  document.body.replaceChildren()
})

describe("mind map viewer", () => {
  it("draws the outline and exposes it as a tree, with a Fit control", async () => {
    const user = userEvent.setup()
    // The Fit control portals into the panel header's actions slot, so the
    // test provides a stand-in for it, attached to the document like the
    // real one so `screen` queries (which search document.body) find it.
    const actionsContainer = document.body.appendChild(
      document.createElement("div")
    )
    render(
      <MindmapViewer markdown={outline} actionsContainer={actionsContainer} />
    )

    const tree = await screen.findByRole("list", { name: "Mind map" })
    expect(tree.textContent).toContain("Saturn")
    expect(tree.textContent).toContain("Made of ice")
    expect(markmap.setData).toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Fit mind map" }))
    expect(markmap.fit).toHaveBeenCalled()
  })
})
