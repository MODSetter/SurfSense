import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { stubPrivacyBridge } from "@/features/privacy-choices/stub-privacy-bridge"
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

  it("names where update checks go and lists usage statistics beside them", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const bridge = stubPrivacyBridge({
      usageStatistics: {
        enabled: false,
        lastSent: { at: "2026-10-20T09:00:00Z", body: { schema: 1 } },
      },
    })
    const user = userEvent.setup()
    render(<NetworkSettings />)

    expect(
      await screen.findByText(
        /updates\.surfsense\.com, falls back to github\.com/
      )
    ).toBeTruthy()
    expect(await screen.findByText(/usage\.surfsense\.com/)).toBeTruthy()
    const usage = screen.getByRole("checkbox", {
      name: "Allow Usage statistics",
    })
    expect(usage.getAttribute("aria-checked")).toBe("false")
    await user.click(usage)

    await waitFor(() => expect(usage.getAttribute("aria-checked")).toBe("true"))
    expect(bridge.calls).toEqual(["usage:true"])
  })

  it("holds a row a policy locked, and says why", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    stubPrivacyBridge({
      updates: { locked: true },
      usageStatistics: { locked: true, lockedReason: "do_not_track" },
    })
    render(<NetworkSettings />)

    const updates = await screen.findByRole("checkbox", {
      name: "Allow App updates",
    })
    await waitFor(() =>
      expect(updates.hasAttribute("data-disabled")).toBe(true)
    )
    expect(
      screen
        .getByRole("checkbox", { name: "Allow Usage statistics" })
        .hasAttribute("data-disabled")
    ).toBe(true)
    expect(screen.getByText(/DO_NOT_TRACK/)).toBeTruthy()
  })
})
