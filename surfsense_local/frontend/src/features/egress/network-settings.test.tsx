import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { NetworkSettings } from "./network-settings"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("network settings", () => {
  it("holds the only switch for reaching github.com", async () => {
    // No backend destinations, so the updater's row is the whole list.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const bridge = stubUpdateBridge({
      automatic: false,
      state: { status: "idle" },
    })
    const user = userEvent.setup()
    render(<NetworkSettings />)

    const toggle = await screen.findByRole("checkbox", {
      name: "Allow App updates",
    })
    expect(toggle.getAttribute("aria-checked")).toBe("false")
    await user.click(toggle)

    await waitFor(() =>
      expect(toggle.getAttribute("aria-checked")).toBe("true")
    )
    expect(bridge.calls).toEqual(["automatic:true"])
  })
})
