import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { TooltipProvider } from "@/components/ui/tooltip"

import { RightPanel } from "./right-panel"

function renderPanel(generating: number) {
  return render(
    <TooltipProvider>
      <RightPanel
        inspect={null}
        tab="sources"
        onTabChange={vi.fn()}
        generating={generating}
        studio={null}
        sources={<p>sources</p>}
        artifacts={<p>artifacts</p>}
      />
    </TooltipProvider>
  )
}

afterEach(cleanup)

describe("right panel", () => {
  it("counts generating artifacts on the artifacts tab", () => {
    renderPanel(2)

    const tab = screen.getByRole("tab", { name: "Artifacts, 2 generating" })
    expect(tab.textContent).toBe("2")
  })

  it("shows a plain tab when nothing is generating", () => {
    renderPanel(0)

    const tab = screen.getByRole("tab", { name: "Artifacts" })
    expect(tab.textContent).toBe("")
  })
})
