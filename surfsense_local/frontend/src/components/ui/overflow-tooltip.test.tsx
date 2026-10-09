import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { OverflowTooltip } from "./overflow-tooltip"
import { TooltipProvider } from "./tooltip"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const NAME = "quarterly-board-report-final-revised.pdf"

// jsdom lays nothing out: give the text the widths a narrow row would.
function cutOff(element: HTMLElement, cut = true) {
  Object.defineProperty(element, "scrollWidth", {
    configurable: true,
    value: cut ? 320 : 120,
  })
  Object.defineProperty(element, "clientWidth", {
    configurable: true,
    value: 120,
  })
}

describe("overflow tooltip", () => {
  it("shows the whole text on hover while it is cut off, and keeps the click", async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <OverflowTooltip
          label={NAME}
          render={
            <button type="button" onClick={onClick}>
              {NAME}
            </button>
          }
        />
      </TooltipProvider>
    )

    const title = screen.getByRole("button", { name: NAME })
    // The name is already the button's; a description would repeat it.
    expect(title.getAttribute("aria-describedby")).toBeNull()
    cutOff(title)
    await user.hover(title)

    expect((await screen.findByRole("tooltip")).textContent).toBe(NAME)
    await user.click(title)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("stays closed while the text fits", async () => {
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <OverflowTooltip label="notes.md" render={<button>notes.md</button>} />
      </TooltipProvider>
    )

    const title = screen.getByRole("button", { name: "notes.md" })
    cutOff(title, false)
    await user.hover(title)
    // Past the provider's 350 ms open delay.
    await act(() => new Promise((resolve) => setTimeout(resolve, 500)))

    expect(screen.queryByRole("tooltip")).toBeNull()
  })

  it("opens while the row that holds keyboard focus for the text is focused", async () => {
    // jsdom never matches :focus-visible; a keyboard user's focus would.
    const matches = Element.prototype.matches
    vi.spyOn(Element.prototype, "matches").mockImplementation(function (
      this: Element,
      selector: string
    ) {
      return selector === ":focus-visible"
        ? this === document.activeElement
        : matches.call(this, selector)
    })
    render(
      <TooltipProvider>
        <ul role="tree">
          <li role="treeitem" tabIndex={0} aria-label={NAME}>
            <OverflowTooltip
              label={NAME}
              focusOwner='[role="treeitem"]'
              render={<span>{NAME}</span>}
            />
          </li>
          <li role="treeitem" tabIndex={-1} aria-label="notes.md">
            notes.md
          </li>
        </ul>
      </TooltipProvider>
    )

    cutOff(screen.getByText(NAME))
    act(() => screen.getByRole("treeitem", { name: NAME }).focus())
    expect((await screen.findByRole("tooltip")).textContent).toBe(NAME)

    act(() => screen.getByRole("treeitem", { name: "notes.md" }).focus())
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull())
  })
})
