import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster } from "sonner"

import { render } from "@/test-utils"

import { ThirdPartyNotices } from "./third-party-notices"

function stubBridge(openResult = "") {
  const openNotices = vi.fn(async () => openResult)
  window.surfsense = {
    ...window.surfsense!,
    about: { details: vi.fn(), openNotices },
  }
  return { openNotices }
}

function renderWithToasts() {
  render(
    <>
      <ThirdPartyNotices />
      <Toaster />
    </>
  )
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("ThirdPartyNotices", () => {
  it("opens the notices the app ships", async () => {
    const { openNotices } = stubBridge()
    const user = userEvent.setup()
    renderWithToasts()

    await user.click(
      screen.getByRole("button", { name: "Third-party notices" })
    )

    expect(openNotices).toHaveBeenCalledOnce()
    expect(
      screen.queryByText("Couldn’t open the third-party notices")
    ).toBeNull()
  })

  it("says why when they cannot be opened", async () => {
    stubBridge("No application is associated with this file")
    const user = userEvent.setup()
    renderWithToasts()

    await user.click(
      screen.getByRole("button", { name: "Third-party notices" })
    )

    expect(
      await screen.findByText("Couldn’t open the third-party notices")
    ).toBeTruthy()
    expect(
      screen.getByText("No application is associated with this file")
    ).toBeTruthy()
  })

  it("shows nothing outside the desktop app", () => {
    render(<ThirdPartyNotices />)

    expect(
      screen.queryByRole("button", { name: "Third-party notices" })
    ).toBeNull()
  })
})
