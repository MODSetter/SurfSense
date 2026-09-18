import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EgressPrompt } from "@/features/egress/egress-prompt"
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

// The prompt lives beside the app shell in main.tsx, and the footer reaches it
// through a module-level seam, so it has to be mounted for a click to ask.
function renderFooter(onOpenLicense: () => void = vi.fn()) {
  return render(
    <>
      <SidebarFooter onOpenLicense={onOpenLicense} />
      <EgressPrompt />
    </>
  )
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
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    const { container } = renderFooter()

    // No bridge and nothing known yet: the strip goes rather than leaving a
    // bordered gap above the bottom edge.
    expect(container.textContent).toBe("")
  })
})

describe("the update row", () => {
  it("checks on demand, then offers the restart once one is ready", async () => {
    stubLicense(license("active"))
    const bridge = stubUpdateBridge({
      automatic: true,
      state: { status: "idle" },
    })
    const user = userEvent.setup()
    renderFooter()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    expect(bridge.calls).toEqual(["check"])

    bridge.push({ status: "downloading", version: "1.0.1" })
    const downloading = await screen.findByRole("button", {
      name: "Downloading…",
    })
    // Clicking mid-download would only start a second check.
    expect((downloading as HTMLButtonElement).disabled).toBe(true)

    bridge.push({ status: "ready", version: "1.0.1" })
    await user.click(
      await screen.findByRole("button", { name: "Restart to update" })
    )

    expect(bridge.calls).toEqual(["check", "install"])
  })

  it("asks before the first check, and checks once allowed", async () => {
    stubLicense(license("active"))
    const bridge = stubUpdateBridge({
      automatic: false,
      state: { status: "idle" },
    })
    const user = userEvent.setup()
    renderFooter()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )

    // Named like any other destination, because that is what it is.
    await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(bridge.calls).toEqual([])

    await user.click(screen.getByRole("button", { name: "Allow" }))

    // Allowing is what Settings > Network's switch does, then the call runs.
    await waitFor(() =>
      expect(bridge.calls).toEqual(["automatic:true", "check"])
    )
  })

  it("cancelling leaves github.com alone", async () => {
    stubLicense(license("active"))
    const bridge = stubUpdateBridge({
      automatic: false,
      state: { status: "idle" },
    })
    const user = userEvent.setup()
    renderFooter()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    await screen.findByRole("alertdialog")
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
    expect(bridge.calls).toEqual([])
  })

  it("installs an update already downloaded without asking", async () => {
    stubLicense(license("active"))
    const bridge = stubUpdateBridge({
      automatic: false,
      state: { status: "ready", version: "1.0.1" },
    })
    const user = userEvent.setup()
    renderFooter()

    // Installing touches no network, so it needs no permission even though
    // checking for this update would.
    await user.click(
      await screen.findByRole("button", { name: "Restart to update" })
    )

    expect(bridge.calls).toEqual(["install"])
    expect(screen.queryByRole("alertdialog")).toBeNull()
  })

  it("renders no update row outside the desktop app", async () => {
    stubLicense(license("active"))
    renderFooter()

    // The license still reports; only the bridge-backed row is missing.
    await screen.findByRole("button", { name: "License active" })

    expect(screen.queryByRole("button", { name: /update/i })).toBeNull()
  })
})
