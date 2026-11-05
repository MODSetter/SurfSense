import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { PluginIcon } from "./plugin-icon"

function renderIcon() {
  const { container } = render(
    <PluginIcon id="notion" name="Notion" hasIcon firstParty />
  )
  return container.querySelector("img") as HTMLImageElement
}

describe("PluginIcon", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    cleanup()
  })

  it("keeps a logo hidden until it has loaded, then fades it in", () => {
    const logo = renderIcon()
    expect(logo.className).toContain("opacity-0")

    fireEvent.load(logo)

    expect(logo.className).toContain("opacity-100")
    expect(logo.className).toContain("transition-opacity")
  })

  it("shows a logo the browser already holds at once", () => {
    vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(
      true
    )
    vi.spyOn(HTMLImageElement.prototype, "naturalWidth", "get").mockReturnValue(
      32
    )

    expect(renderIcon().className).toContain("opacity-100")
  })

  it("falls back to the name's first letter when the logo fails", () => {
    fireEvent.error(renderIcon())

    expect(screen.getByText("N")).toBeTruthy()
  })
})
