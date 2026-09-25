import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { AboutSettings } from "./about-settings"

const DETAILS = {
  version: "2.0.2",
  electron: "44.0.0",
  chrome: "146.0.1",
  node: "24.1.0",
  os: "macOS 15.4",
  arch: "arm64",
}

function stubAboutBridge() {
  stubUpdateBridge({ automatic: true, state: { status: "idle" } })
  const openExternal = vi.fn(async () => undefined)
  window.surfsense = {
    ...window.surfsense!,
    openExternal,
    about: { details: async () => DETAILS },
  }
  return { openExternal }
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("AboutSettings", () => {
  it("shows the running version beside the update controls", async () => {
    stubAboutBridge()
    render(<AboutSettings />)

    expect(await screen.findByText("Version 2.0.2")).toBeTruthy()
    // The heading scrolls with the page, as the model sections' do, so the
    // fade never cuts the app's name under a fixed header.
    expect(
      document
        .querySelector('[data-slot="scroll-fade-viewport"]')
        ?.contains(screen.getByRole("heading", { name: "About" }))
    ).toBe(true)
    expect(
      await screen.findByRole("button", { name: "Check now" })
    ).toBeTruthy()
  })

  it("opens this version's release notes in the browser", async () => {
    const bridge = stubAboutBridge()
    const user = userEvent.setup()
    render(<AboutSettings />)

    await user.click(await screen.findByRole("link", { name: "Release notes" }))

    expect(bridge.openExternal).toHaveBeenCalledWith(
      "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2"
    )
  })

  it("copies the version and system for a bug report", async () => {
    stubAboutBridge()
    const user = userEvent.setup()
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined)
    render(<AboutSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Copy system info" })
    )

    const copied = writeText.mock.calls[0]?.[0] ?? ""
    expect(copied).toContain("SurfSense 2.0.2")
    expect(copied).toContain("macOS 15.4 (arm64)")
    expect(copied).toContain("Electron 44.0.0")
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy()
  })
})
