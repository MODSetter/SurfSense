import { BrowserWindow, session } from "electron"

import { confineSnapshotSession } from "./confine-snapshot-session.ts"
import type { PrintDocx } from "./serve-snapshots.ts"
import { snapshotPageFailure } from "./snapshot-page-answer.ts"

// In memory only, and apart from the app's session: nothing a document does
// there reaches the app's storage, cache or service workers.
const PARTITION = "docx-snapshot"
// The API draws only the first four pages (previews/page_images.py PAGE_LIMIT),
// and printing the rest only makes the upload bigger.
const PAGES_DRAWN = "1-4"

/**
 * Print Word files with the frontend's snapshot page (docx-snapshot.html), in a
 * window the user never sees. The page lays the file out with docx-preview, and
 * `window.docxSnapshot` resolves to null once its pages, images and fonts are in
 * place, or to the reason it could not. Call once the app is ready.
 */
export function printInHiddenWindow(page: URL): PrintDocx {
  const snapshotSession = session.fromPartition(PARTITION)
  const allow = confineSnapshotSession(snapshotSession, page)

  return async (fileUrl, signal) => {
    const win = new BrowserWindow({
      show: false,
      webPreferences: {
        session: snapshotSession,
        // The page needs nothing from the app: no preload, no Node, its own process.
        sandbox: true,
        contextIsolation: true,
        nodeIntegration: false,
        // A hidden window's timers are throttled otherwise, which slows the layout.
        backgroundThrottling: false,
      },
    })
    const stay = (event: Electron.Event) => event.preventDefault()
    win.webContents.on("will-navigate", stay)
    win.webContents.on("will-frame-navigate", stay)
    const consoleErrors: string[] = []
    win.webContents.on("console-message", ({ level, message }) => {
      if (level === "error") consoleErrors.push(message)
    })
    const release = allow(fileUrl)
    const close = () => win.destroy()
    signal.addEventListener("abort", close, { once: true })
    try {
      const url = new URL(page)
      url.searchParams.set("file", fileUrl)
      await win.loadURL(url.href)
      // A rejected promise reaches here without its message, so the page resolves its reason.
      const answer: unknown = await win.webContents.executeJavaScript("window.docxSnapshot")
      const failure = snapshotPageFailure(answer, consoleErrors)
      if (failure !== null) throw new Error(failure)
      return await win.webContents.printToPDF({
        // The page sets @page from the document's own size and margins.
        preferCSSPageSize: true,
        printBackground: true,
        pageRanges: PAGES_DRAWN,
      })
    } finally {
      release()
      signal.removeEventListener("abort", close)
      if (!win.isDestroyed()) win.destroy()
    }
  }
}
