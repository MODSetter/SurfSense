import type { ReactElement } from "react"
import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
} from "./alert-dialog"
import { Dialog, DialogContent, DialogTitle } from "./dialog"

// Callers clear what a dialog shows in the same update that closes it.
const modals: [string, (target: string | null) => ReactElement][] = [
  [
    "dialog",
    (target) => (
      <Dialog open={target !== null}>
        <DialogContent>
          <DialogTitle>{target ? `Delete ${target}?` : "Delete?"}</DialogTitle>
        </DialogContent>
      </Dialog>
    ),
  ],
  [
    "alert dialog",
    (target) => (
      <AlertDialog open={target !== null}>
        <AlertDialogContent>
          <AlertDialogTitle>
            {target ? `Delete ${target}?` : "Delete?"}
          </AlertDialogTitle>
        </AlertDialogContent>
      </AlertDialog>
    ),
  ],
]

afterEach(cleanup)

describe.each(modals)("%s closing", (_, modal) => {
  it("keeps showing what it showed while open", () => {
    const { rerender } = render(modal("Report.pdf"))

    rerender(modal(null))

    expect(screen.getByText("Delete Report.pdf?")).toBeTruthy()
    expect(screen.queryByText("Delete?")).toBeNull()
  })

  it("shows fresh content when reopened", () => {
    const { rerender } = render(modal("Report.pdf"))
    rerender(modal(null))

    rerender(modal("Notes.md"))

    expect(screen.getByText("Delete Notes.md?")).toBeTruthy()
  })
})
