import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { EditsBadge } from "./edits-badge"

afterEach(cleanup)

describe("edits badge", () => {
  it("names itself in full, since its tooltip is only seen", () => {
    render(<EditsBadge />)

    expect(screen.getByText("Edits")).toBeTruthy()
    expect(
      screen.getByRole("note", { name: "Edits: can edit pictures" })
    ).toBeTruthy()
  })

  it("opens its tooltip on keyboard focus as on hover", async () => {
    const user = userEvent.setup()
    render(<EditsBadge />)

    await user.tab()

    expect(document.activeElement?.textContent).toBe("Edits")
    expect(await screen.findByText("Can edit pictures")).toBeTruthy()
  })
})
