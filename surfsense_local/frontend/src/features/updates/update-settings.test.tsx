import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import {
  UpdateBanner,
  UpdateSettings,
  type UpdateState,
} from "./update-settings"

function stubBridge(initial: { automatic: boolean; state: UpdateState }) {
  let prefs = { automatic: initial.automatic }
  let state = initial.state
  const listeners = new Set<(state: UpdateState) => void>()
  const calls: string[] = []
  window.surfsense = {
    apiUrl: "",
    platform: "darwin",
    openDocument: vi.fn(),
    revealDocument: vi.fn(),
    updates: {
      prefs: async () => prefs,
      setAutomatic: async (automatic: boolean) => {
        calls.push(`automatic:${automatic}`)
        prefs = { automatic }
        return prefs
      },
      state: async () => state,
      check: async () => {
        calls.push("check")
      },
      install: async () => {
        calls.push("install")
      },
      onState: (listener) => {
        listeners.add(listener)
        return () => listeners.delete(listener)
      },
    },
  }
  return {
    calls,
    push(next: UpdateState) {
      state = next
      for (const listener of listeners) listener(next)
    },
  }
}

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("UpdateSettings", () => {
  it("is off by default and remembers being turned on", async () => {
    const bridge = stubBridge({ automatic: false, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    const toggle = await screen.findByRole("checkbox", {
      name: "Check for updates automatically",
    })
    expect(toggle).toHaveProperty("checked", false)
    await user.click(toggle)

    await waitFor(() => expect(toggle).toHaveProperty("checked", true))
    expect(bridge.calls).toEqual(["automatic:true"])
  })

  it("checks on demand and reports each state", async () => {
    const bridge = stubBridge({ automatic: false, state: { status: "idle" } })
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

describe("UpdateBanner", () => {
  it("appears only when an update is ready and restarts on click", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<UpdateBanner />)

    expect(screen.queryByRole("status")).toBeNull()
    bridge.push({ status: "ready", version: "1.0.1" })

    const banner = await screen.findByRole("status")
    expect(banner.textContent).toContain("1.0.1")
    await user.click(screen.getByRole("button", { name: "Restart to update" }))
    expect(bridge.calls).toEqual(["install"])
  })
})
