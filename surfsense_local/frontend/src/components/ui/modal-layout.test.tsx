import type { ReactElement } from "react"
import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, waitFor } from "@testing-library/react"

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "./alert-dialog"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog"

const modals: [string, () => ReactElement][] = [
  [
    "dialog",
    () => (
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle>Dialog</DialogTitle>
          <DialogDescription>Dialog content</DialogDescription>
        </DialogContent>
      </Dialog>
    ),
  ],
  [
    "alert dialog",
    () => (
      <AlertDialog defaultOpen>
        <AlertDialogContent>
          <AlertDialogTitle>Alert dialog</AlertDialogTitle>
          <AlertDialogDescription>Alert dialog content</AlertDialogDescription>
        </AlertDialogContent>
      </AlertDialog>
    ),
  ],
]

afterEach(() => {
  cleanup()
  document.documentElement.classList.remove("electron-macos", "electron")
  document.body.replaceChildren()
})

describe.each(modals)("%s app-shell layout", (_name, renderModal) => {
  it("keeps Electron title-bar spacing off the scroll-locked body", async () => {
    document.documentElement.classList.add("electron-macos")
    const root = document.createElement("div")
    root.id = "root"
    root.style.paddingTop = "28px"
    document.body.append(root)

    render(renderModal(), { container: root })

    await waitFor(() =>
      expect(document.body.hasAttribute("data-scroll-locked")).toBe(true)
    )
    expect(getComputedStyle(document.body).paddingTop).toBe("0px")
    expect(getComputedStyle(root).paddingTop).toBe("28px")
  })
})
