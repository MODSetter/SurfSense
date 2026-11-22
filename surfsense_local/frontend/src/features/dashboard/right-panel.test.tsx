import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { RightPanel } from "./right-panel"

afterEach(cleanup)

describe("the right panel", () => {
  it("puts the toggle on Studio's heading line", () => {
    render(
      <RightPanel
        inspect={null}
        studio={null}
        artifacts={null}
        toggle={<button type="button">Hide right panel</button>}
      />
    )

    const heading = screen.getByRole("heading", { name: "Studio" })
    expect(
      heading.parentElement?.contains(
        screen.getByRole("button", { name: "Hide right panel" })
      )
    ).toBe(true)
  })

  it("shows no toggle over a citation or a Studio result", () => {
    render(
      <RightPanel
        inspect={<p>A preview</p>}
        studio={null}
        artifacts={null}
        toggle={<button type="button">Hide right panel</button>}
      />
    )

    expect(screen.getByText("A preview")).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Hide right panel" })
    ).toBeNull()
  })
})
