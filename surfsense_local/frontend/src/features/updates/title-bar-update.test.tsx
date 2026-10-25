import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { stubUpdateBridge as stubBridge } from "./stub-bridge"
import { TitleBarUpdate } from "./title-bar-update"

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("the title bar's update pill", () => {
  it.each([
    { status: "idle" },
    { status: "checking" },
    { status: "up-to-date" },
    { status: "error", message: "net::ERR_INTERNET_DISCONNECTED" },
  ] as const)(
    "keeps no space while there is nothing to install ($status)",
    (state) => {
      stubBridge({ automatic: true, state })
      const { container } = render(<TitleBarUpdate />)

      expect(container.childElementCount).toBe(0)
    }
  )

  it("shows a download's progress, and how far it got in its label", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    bridge.push({ status: "downloading", version: "1.0.1", percent: 64 })

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading SurfSense 1.0.1",
    })
    expect(progress.getAttribute("aria-valuenow")).toBe("64")
    expect(progress.textContent).toContain("Downloading 64%")
    // A download runs by itself; there is nothing to click.
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("says only that it is downloading until the size is known", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    bridge.push({ status: "downloading", version: "1.0.1", percent: null })

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading SurfSense 1.0.1",
    })
    expect(progress.hasAttribute("aria-valuenow")).toBe(false)
    expect(progress.textContent).toContain("Downloading…")
  })

  it("restarts into a downloaded update, once", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)
    bridge.push({ status: "ready", version: "1.0.1" })

    const button = await screen.findByRole("button", {
      name: "Restart to install 1.0.1",
    })
    expect(button.textContent).toContain("Update")
    await user.click(button)

    expect(bridge.calls).toEqual(["install"])
    expect(button.hasAttribute("disabled")).toBe(true)
  })

  it("says what it does in its own label, with no tooltip", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)
    bridge.push({ status: "ready", version: "1.0.1" })

    await user.hover(
      await screen.findByRole("button", { name: "Restart to install 1.0.1" })
    )

    expect(screen.queryByRole("tooltip")).toBeNull()
  })
})
