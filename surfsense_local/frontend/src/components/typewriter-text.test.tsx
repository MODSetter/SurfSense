import { act, render } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TypewriterText } from "./typewriter-text"

function reducedMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({ matches }),
  })
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe("TypewriterText", () => {
  it("clears the placeholder before revealing the generated title", () => {
    vi.useFakeTimers()
    reducedMotion(false)
    const view = render(<TypewriterText text="New chat" />)

    view.rerender(<TypewriterText text="Revenue Growth" />)

    const visual = view.container.querySelector('[aria-hidden="true"]')
    expect(visual?.textContent).toBe("")
    expect(view.container.querySelector(".sr-only")?.textContent).toBe(
      "Revenue Growth"
    )

    act(() => vi.advanceTimersByTime(35))
    expect(visual?.textContent).toBe("R")

    act(() => vi.runAllTimers())
    expect(visual?.textContent).toBe("Revenue Growth")
  })

  it("shows the final title immediately when reduced motion is requested", () => {
    reducedMotion(true)
    const view = render(<TypewriterText text="New chat" />)

    view.rerender(<TypewriterText text="Revenue Growth" />)

    expect(
      view.container.querySelector('[aria-hidden="true"]')?.textContent
    ).toBe("Revenue Growth")
  })
})
