import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { SourceScope } from "./api"
import { WorkingFrom } from "./working-from"

function scopeOf(titles: string[]): SourceScope {
  return { document_ids: titles.map((_, index) => index + 1), titles }
}

afterEach(cleanup)

describe("WorkingFrom", () => {
  it("names a single source", () => {
    render(<WorkingFrom scope={scopeOf(["Plan.pdf"])} />)

    expect(screen.getByText("Working from Plan.pdf")).toBeTruthy()
  })

  it("names up to three sources inline", () => {
    render(<WorkingFrom scope={scopeOf(["Plan", "Budget", "Memo"])} />)

    expect(screen.getByText("Working from Plan, Budget, and Memo")).toBeTruthy()
  })

  it("counts more than three and names them on hover", async () => {
    const user = userEvent.setup()
    render(
      <WorkingFrom scope={scopeOf(["Plan", "Budget", "Memo", "Contract"])} />
    )

    const line = screen.getByText("Working from 4 sources")
    expect(screen.queryByText(/Contract/)).toBeNull()
    await user.hover(line)

    expect(
      await screen.findByText("Plan, Budget, Memo, and Contract")
    ).toBeTruthy()
  })

  it("says when no sources were selected", () => {
    render(<WorkingFrom scope={scopeOf([])} />)

    expect(screen.getByText("Working from no sources")).toBeTruthy()
  })

  it("shows nothing for a turn that named no selection", () => {
    const { container } = render(<WorkingFrom scope={null} />)

    expect(container.textContent).toBe("")
  })
})
