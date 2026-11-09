import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"

import { stubUpdateBridge as stubBridge } from "./stub-bridge"
import { UpdateSettings } from "./update-settings"

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("UpdateSettings", () => {
  it("asks before checking while App updates are switched off", async () => {
    const bridge = stubBridge({ automatic: false, state: { status: "idle" } })
    const user = userEvent.setup()
    render(
      <>
        <UpdateSettings />
        <EgressPrompt />
      </>
    )

    await user.click(await screen.findByRole("button", { name: "Check now" }))

    // Network promises github.com is not contacted until allowed, so the
    // first check asks rather than going ahead.
    const dialog = await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(bridge.calls).toEqual([])
    // An Electron main without the privacy bridge still reads GitHub's
    // releases, so neither the question nor the row names SurfSense's feed.
    expect(dialog.textContent).toContain(
      "reads the list of releases on github.com"
    )
    expect(dialog.textContent).not.toContain("updates.surfsense.com")
    expect(screen.getByText(/Free updates from GitHub\./)).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(bridge.calls).toEqual(["automatic:true", "check"])
    )
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
    bridge.push({ status: "downloading", version: "1.0.1", percent: null })
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

    // The version the restart lands on, named where the decision is made,
    // and that quitting installs it too.
    expect(
      await screen.findByText(
        "SurfSense 1.0.1 is ready. It installs when you restart or the next time you quit."
      )
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
