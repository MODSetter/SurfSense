import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { LicenseStatus } from "@/features/license/api"
import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { SidebarFooter } from "./sidebar-footer"

function license(state: LicenseStatus["state"]): LicenseStatus {
  return { state, plan: null, email: null, expiry: null, max_users: null }
}

function stubLicense(status: LicenseStatus) {
  const fetches = vi.fn(async (input: RequestInfo | URL) =>
    String(input) === "/license/status"
      ? Response.json(status)
      : Response.json([])
  )
  vi.stubGlobal("fetch", fetches)
  return fetches
}

function renderFooter(onOpenLicense: () => void = vi.fn()) {
  return render(<SidebarFooter onOpenLicense={onOpenLicense} />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("the license row", () => {
  it("opens Settings, so the row is a way in and not just a light", async () => {
    stubLicense(license("none"))
    const onOpenLicense = vi.fn()
    const user = userEvent.setup()
    renderFooter(onOpenLicense)

    await user.click(await screen.findByRole("button", { name: "No license" }))

    expect(onOpenLicense).toHaveBeenCalledOnce()
  })

  it.each([
    ["none", "No license"],
    ["license_expired", "License expired"],
    ["clock_untrusted", "Clock is off"],
  ] as const)("shows %s in red", async (state, label) => {
    stubLicense(license(state))
    renderFooter()

    const row = await screen.findByRole("button", { name: label })

    // Plugins stay locked in all three, so all three read the same.
    expect(row.className).toContain("text-destructive")
  })

  it("shows an active license in green", async () => {
    stubLicense(license("active"))
    stubUpdateBridge({ automatic: true, state: { status: "idle" } })
    renderFooter()

    const row = await screen.findByRole("button", { name: "License active" })

    expect(row.className).toContain("text-emerald-600")
    // Ghost buttons repaint their text on hover; green that survives the
    // pointer is the difference between a status light and decoration.
    expect(row.className).toContain("hover:text-emerald-600")
  })

  it("stays out of the way until the status arrives", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {}))
    )
    const { container } = renderFooter()

    // No bridge and nothing known yet: the strip goes rather than leaving a
    // bordered gap above the bottom edge.
    expect(container.textContent).toBe("")
  })
})

describe("updates", () => {
  it("are not in the footer: the title bar shows them", async () => {
    stubLicense(license("active"))
    stubUpdateBridge({
      automatic: true,
      state: { status: "ready", version: "1.0.1" },
    })
    renderFooter()

    await screen.findByRole("button", { name: "License active" })
    expect(screen.queryByRole("button", { name: /update/i })).toBeNull()
  })

  it("leave no footer at all when there is no license status", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Promise<Response>(() => undefined))
    )
    stubUpdateBridge({ automatic: true, state: { status: "idle" } })
    const { container } = renderFooter()

    expect(container.querySelector(".border-t")).toBeNull()
  })
})
