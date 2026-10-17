import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster } from "sonner"

import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { IssueReportDialog } from "./issue-report-dialog"
import { SidecarCrashReporter } from "./sidecar-crash-reporter"

type Crash = { name: string; code: number | null }

function stubCrashBridge() {
  stubUpdateBridge({ automatic: true, state: { status: "idle" } })
  let listener: ((crash: Crash) => void) | undefined
  window.surfsense = {
    ...window.surfsense!,
    sidecars: {
      onCrash: (next) => {
        listener = next
        return () => {
          if (listener === next) listener = undefined
        }
      },
    },
  } as Window["surfsense"]
  return {
    crash: (event: Crash) => listener?.(event),
    isListening: () => listener !== undefined,
  }
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("sidecar crash reports", () => {
  it("names the affected feature and carries diagnostics into Report issue", async () => {
    const bridge = stubCrashBridge()
    const user = userEvent.setup()
    const view = render(
      <>
        <SidecarCrashReporter />
        <IssueReportDialog />
        <Toaster />
      </>
    )
    expect(bridge.isListening()).toBe(true)

    act(() => bridge.crash({ name: "worker-ingest", code: 7 }))

    expect(await screen.findByText("Document processing stopped")).toBeTruthy()
    expect(screen.queryByText(/worker-ingest|code=7/)).toBeNull()
    await user.click(screen.getByRole("button", { name: "Report issue" }))

    const dialog = await screen.findByRole("dialog", {
      name: "Report an issue",
    })
    expect(
      within(dialog).getByText("Error: Sidecar worker-ingest crashed (code=7)")
    ).toBeTruthy()

    view.unmount()
    expect(bridge.isListening()).toBe(false)
  })

  it("names the agent, and says it tries again rather than asking for a restart", async () => {
    const bridge = stubCrashBridge()
    render(
      <>
        <SidecarCrashReporter />
        <Toaster />
      </>
    )

    act(() => bridge.crash({ name: "opencode", code: 1 }))

    // sonner keeps an earlier test's toasts, so read this one alone.
    const toast = (
      await screen.findByText("The agent stopped")
    ).closest<HTMLElement>("[data-sonner-toast]")!
    expect(
      within(toast).getByText(
        "SurfSense will try again with your next Agentic message."
      )
    ).toBeTruthy()
    expect(
      within(toast).queryByText("Restart SurfSense to restore it.")
    ).toBeNull()
  })
})
