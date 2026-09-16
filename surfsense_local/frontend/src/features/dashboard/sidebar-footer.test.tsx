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
  it("invites a free user to unlock plugins, and opens Settings", async () => {
    stubLicense(license("none"))
    const onOpenLicense = vi.fn()
    const user = userEvent.setup()
    renderFooter(onOpenLicense)

    const row = await screen.findByRole("button", { name: "Unlock plugins" })
    await user.click(row)

    expect(onOpenLicense).toHaveBeenCalledOnce()
    // The app is free, so owning no license is not a fault and must not read
    // like one. This is the difference between an invitation and a nag.
    expect(row.className).not.toContain("amber")
  })

  it.each([
    ["license_expired", "License expired"],
    ["clock_untrusted", "Clock is off"],
  ] as const)("flags %s, in the colour of a problem", async (state, label) => {
    stubLicense(license(state))
    renderFooter()

    const row = await screen.findByRole("button", { name: label })

    expect(row.className).toContain("amber")
  })

  it("says nothing once a license is active", async () => {
    const fetches = stubLicense(license("active"))
    stubUpdateBridge({ automatic: true, state: { status: "idle" } })
    renderFooter()

    await screen.findByRole("button", { name: "Check for updates" })
    await waitFor(() => expect(fetches).toHaveBeenCalled())

    expect(screen.queryByRole("button", { name: "Unlock plugins" })).toBeNull()
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

  it("renders nothing outside the desktop app", async () => {
    const fetches = stubLicense(license("active"))
    const { container } = renderFooter()

    await waitFor(() => expect(fetches).toHaveBeenCalled())

    // No bridge and no license to report: the strip goes rather than leaving a
    // bordered gap above the bottom edge.
    expect(container.textContent).toBe("")
  })
})
