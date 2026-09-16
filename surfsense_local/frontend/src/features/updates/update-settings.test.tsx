import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { stubUpdateBridge as stubBridge } from "./stub-bridge"
import { UpdateSettings } from "./update-settings"

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("UpdateSettings", () => {
  it("cannot check while App updates are switched off", async () => {
    const bridge = stubBridge({ automatic: false, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    // The one switch is a section away in Network, so this points at it
    // rather than stacking a consent dialog on the dialog already open.
    const check = await screen.findByRole("button", { name: "Check now" })
    expect((check as HTMLButtonElement).disabled).toBe(true)
    await user.click(check)

    expect(bridge.calls).toEqual([])
  })

  it("checks on demand and reports each state", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    await user.click(await screen.findByRole("button", { name: "Check now" }))
    expect(bridge.calls).toEqual(["check"])

    bridge.push({ status: "checking" })
    expect(await screen.findByText("Checking…")).toBeTruthy()
    bridge.push({ status: "up-to-date" })
    expect(await screen.findByText("SurfSense is up to date")).toBeTruthy()
    bridge.push({ status: "downloading", version: "1.0.1" })
    expect(await screen.findByText("Downloading 1.0.1…")).toBeTruthy()
    bridge.push({ status: "error", message: "net::ERR_INTERNET_DISCONNECTED" })
    expect((await screen.findByRole("alert")).textContent).toContain(
      "ERR_INTERNET_DISCONNECTED"
    )
  })

  it("offers to restart once the update is downloaded", async () => {
    const bridge = stubBridge({
      automatic: true,
      state: { status: "ready", version: "1.0.1" },
    })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    // The version the restart lands on, named where the decision is made.
    expect(
      await screen.findByText("SurfSense 1.0.1 is ready to install")
    ).toBeTruthy()
    await user.click(
      await screen.findByRole("button", { name: "Restart to update" })
    )

    expect(bridge.calls).toEqual(["install"])
  })

  it("renders nothing outside the desktop app", () => {
    const { container } = render(<UpdateSettings />)

    expect(container.textContent).toBe("")
  })
})
