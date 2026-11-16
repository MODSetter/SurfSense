import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { LicenseStatus } from "@/features/license/api"
import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { SidebarFooter } from "./sidebar-footer"

function license(state: LicenseStatus["state"]): LicenseStatus {
  return {
    state,
    plan: null,
    email: null,
    expiry: null,
    max_users: null,
    firm: null,
    jobs: [],
  }
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

    // Nothing known yet: no row guesses at the license, and the guides stay.
    expect(container.textContent).toBe("Guides and videos")
  })
})

describe("the guides row", () => {
  it("opens the guides by area, each a link to its page on surfsense.com", async () => {
    stubLicense(license("none"))
    const user = userEvent.setup()
    renderFooter()

    await user.click(screen.getByRole("button", { name: "Guides and videos" }))

    const dialog = await screen.findByRole("dialog", {
      name: "Guides and videos",
    })
    const area = within(dialog).getByRole("region", { name: "Jobs" })
    const guide = within(area).getByRole("link", {
      name: "Fill in a security questionnaire from your policies",
    })
    const url = new URL(guide.getAttribute("href") ?? "")
    expect(url.origin + url.pathname).toBe(
      "https://www.surfsense.com/docs/v2/guides/security-questionnaire"
    )
    // Tagged like every other surfsense.com link: where in the app it was opened.
    expect(url.searchParams.get("utm_content")).toBe("guides_dialog")
    const hub = within(dialog).getByRole("link", {
      name: "All guides on surfsense.com",
    })
    expect(new URL(hub.getAttribute("href") ?? "").pathname).toBe(
      "/docs/v2/guides"
    )
  })

  it("lists every guide on the site once", async () => {
    stubLicense(license("none"))
    const user = userEvent.setup()
    renderFooter()

    await user.click(screen.getByRole("button", { name: "Guides and videos" }))

    const dialog = await screen.findByRole("dialog", {
      name: "Guides and videos",
    })
    const pages = within(dialog)
      .getAllByRole("link")
      .map((link) => new URL(link.getAttribute("href") ?? "").pathname)
      .filter((path) => path !== "/docs/v2/guides")
    expect(pages).toHaveLength(27)
    expect(new Set(pages).size).toBe(27)
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

  it("add no row while there is no license status", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Promise<Response>(() => undefined))
    )
    stubUpdateBridge({ automatic: true, state: { status: "idle" } })
    renderFooter()

    expect(screen.getAllByRole("button")).toHaveLength(1)
    expect(screen.queryByRole("button", { name: /update/i })).toBeNull()
  })
})
