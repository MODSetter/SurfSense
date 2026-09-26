import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent, { type UserEvent } from "@testing-library/user-event"
import { Toaster } from "sonner"

import { AppDialogs } from "@/components/ui/app-dialog-slot"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import { render } from "@/test-utils"

import { errorToast } from "./error-toast"
import { IssueReportDialog } from "./issue-report-dialog"
import { openIssueReport } from "./issue-report-state"

const DETAILS = {
  version: "2.0.2",
  electron: "44.0.0",
  chrome: "146.0.1",
  node: "24.1.0",
  os: "macOS 15.4",
  arch: "arm64",
}

const LOG = [
  "18:21:03 [api] Traceback (most recent call last):",
  "18:21:03 [api] KeyError: 'model'",
]

const ERROR = "Couldn’t load this chat: Request failed with status 500"

function stubBridge() {
  stubUpdateBridge({ automatic: true, state: { status: "idle" } })
  const openExternal = vi.fn<(url: string) => Promise<void>>(
    async () => undefined
  )
  window.surfsense = {
    ...window.surfsense!,
    openExternal,
    about: { details: async () => DETAILS },
    sessionLog: { read: async () => LOG },
  }
  return { openExternal }
}

async function openWithLog(context?: { error?: string }) {
  render(<IssueReportDialog />)
  act(() => openIssueReport(context))
  await screen.findByText(/KeyError: 'model'/)
}

async function describeIssue(user: UserEvent) {
  await user.type(
    screen.getByRole("textbox", { name: "What went wrong?" }),
    "Chat never answers"
  )
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("issue report", () => {
  it("opens from an error toast, carrying what the toast said", async () => {
    stubBridge()
    const user = userEvent.setup()
    render(
      <>
        <IssueReportDialog />
        <Toaster />
      </>
    )

    act(() => {
      errorToast("Couldn’t load this chat", {
        description: "Request failed with status 500",
      })
    })
    await user.click(
      await screen.findByRole("button", { name: "Report issue" })
    )

    const dialog = await screen.findByRole("dialog", {
      name: "Report an issue",
    })
    expect(within(dialog).getByText(`Error: ${ERROR}`)).toBeTruthy()
  })

  it("opens from the Help menu", async () => {
    stubBridge()
    let reportIssue = () => {}
    window.surfsense!.help = {
      onReportIssue: (listener) => {
        reportIssue = listener
        return () => {}
      },
    }
    render(<IssueReportDialog />)

    act(() => reportIssue())

    expect(
      await screen.findByRole("dialog", { name: "Report an issue" })
    ).toBeTruthy()
  })

  it("keeps the draft when the dialog it opened over closes", async () => {
    stubBridge()
    const user = userEvent.setup()
    const withSettings = (open: boolean) => (
      <AppDialogs dialogs={[IssueReportDialog]}>
        <Dialog open={open}>
          <DialogContent>
            <DialogTitle>Settings</DialogTitle>
          </DialogContent>
        </Dialog>
      </AppDialogs>
    )
    const view = render(withSettings(true))
    act(() => openIssueReport())
    await describeIssue(user)
    await user.keyboard("{Escape}")

    view.rerender(withSettings(false))
    act(() => openIssueReport())

    const draft = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "What went wrong?",
    })
    expect(draft.value).toBe("Chat never answers")
  })

  it("shows this session's log", async () => {
    stubBridge()

    await openWithLog()

    expect(screen.getByRole("log", { name: "Session log" }).textContent).toBe(
      LOG.join("\n")
    )
  })

  it("opens a prefilled bug report once described, and copies the log for it", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined)
    await openWithLog({ error: ERROR })

    const submit = screen.getByRole("button", { name: "Continue on GitHub" })
    expect((submit as HTMLButtonElement).disabled).toBe(true)
    await describeIssue(user)
    await user.click(submit)

    await waitFor(() => expect(bridge.openExternal).toHaveBeenCalledOnce())
    const what =
      new URL(bridge.openExternal.mock.calls[0][0]).searchParams.get("what") ??
      ""
    expect(what).toContain("Chat never answers")
    expect(what).toContain(`Error: ${ERROR}`)
    expect(what).toContain("SurfSense 2.0.2")
    expect(writeText).toHaveBeenCalledExactlyOnceWith(LOG.join("\n"))
  })

  it("leaves the log out when asked to", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined)
    await openWithLog()

    await describeIssue(user)
    await user.click(
      screen.getByRole("checkbox", { name: "Include the session log" })
    )
    await user.click(screen.getByRole("button", { name: "Continue on GitHub" }))

    await waitFor(() => expect(bridge.openExternal).toHaveBeenCalledOnce())
    expect(writeText).not.toHaveBeenCalled()
  })

  it("keeps GitHub closed when the log can’t be copied", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(
      new Error("Document is not focused.")
    )
    await openWithLog()

    await describeIssue(user)
    await user.click(screen.getByRole("button", { name: "Continue on GitHub" }))

    expect(await screen.findByRole("alert")).toBeTruthy()
    expect(bridge.openExternal).not.toHaveBeenCalled()
  })
})
