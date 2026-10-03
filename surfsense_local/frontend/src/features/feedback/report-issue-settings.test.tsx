import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { ReportIssueSettings } from "./report-issue-settings"

const DETAILS = {
  version: "2.0.2",
  electron: "44.0.0",
  chrome: "146.0.1",
  node: "24.1.0",
  os: "macOS 15.4",
  arch: "arm64",
}

function stubBridge() {
  stubUpdateBridge({ automatic: true, state: { status: "idle" } })
  const openExternal = vi.fn<(url: string) => Promise<void>>(
    async () => undefined
  )
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

describe("ReportIssueSettings", () => {
  it("files a report from the page, with the system details", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<ReportIssueSettings />)

    await user.type(
      await screen.findByRole("textbox", { name: "What went wrong?" }),
      "Settings freezes"
    )
    await user.click(screen.getByRole("button", { name: "Continue on GitHub" }))

    await waitFor(() => expect(bridge.openExternal).toHaveBeenCalledOnce())
    const what =
      new URL(bridge.openExternal.mock.calls[0][0]).searchParams.get("what") ??
      ""
    expect(what).toContain("Settings freezes")
    expect(what).toContain("SurfSense 2.0.2")
  })

  it("copies the system details on their own", async () => {
    stubBridge()
    const user = userEvent.setup()
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined)
    render(<ReportIssueSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Copy system info" })
    )

    expect(writeText.mock.calls[0]?.[0]).toContain("macOS 15.4 (arm64)")
  })
})
