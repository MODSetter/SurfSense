import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen, waitFor } from "@testing-library/react"

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
} from "./alert-dialog"
import { AppDialogs } from "./app-dialog-slot"
import { Dialog, DialogContent, DialogTitle } from "./dialog"

function Report() {
  return (
    <Dialog open>
      <DialogContent>
        <DialogTitle>Report</DialogTitle>
      </DialogContent>
    </Dialog>
  )
}

const APP_DIALOGS = [Report]

afterEach(cleanup)

describe("app dialogs", () => {
  it("open on their own when no dialog is open", async () => {
    render(<AppDialogs dialogs={APP_DIALOGS}>{null}</AppDialogs>)

    expect(await screen.findByRole("dialog", { name: "Report" })).toBeTruthy()
  })

  it("open as the nested dialog of the deepest open dialog", async () => {
    render(
      <AppDialogs dialogs={APP_DIALOGS}>
        <Dialog open>
          <DialogContent>
            <DialogTitle>Chats</DialogTitle>
            <AlertDialog open>
              <AlertDialogContent>
                <AlertDialogTitle>Delete chat?</AlertDialogTitle>
              </AlertDialogContent>
            </AlertDialog>
          </DialogContent>
        </Dialog>
      </AppDialogs>
    )

    expect(
      await screen.findAllByRole("dialog", { name: "Report" })
    ).toHaveLength(1)
    await waitFor(() =>
      expect(
        screen
          .getByText("Delete chat?")
          .closest('[role="alertdialog"]')
          ?.hasAttribute("data-nested-dialog-open")
      ).toBe(true)
    )
  })

  it("move back out when the dialog they opened over closes", async () => {
    const view = render(
      <AppDialogs dialogs={APP_DIALOGS}>
        <Dialog open>
          <DialogContent>
            <DialogTitle>Settings</DialogTitle>
          </DialogContent>
        </Dialog>
      </AppDialogs>
    )
    await screen.findByRole("dialog", { name: "Report" })

    view.rerender(<AppDialogs dialogs={APP_DIALOGS}>{null}</AppDialogs>)

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Settings" })).toBeNull()
    )
    expect(screen.getAllByRole("dialog", { name: "Report" })).toHaveLength(1)
  })
})
