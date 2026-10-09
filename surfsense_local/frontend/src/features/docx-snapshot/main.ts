import { layOutSnapshot } from "./snapshot-page"

declare global {
  interface Window {
    /** Electron awaits it before printing: null when laid out, else the reason. */
    docxSnapshot?: Promise<string | null>
  }
}

window.docxSnapshot = layOutSnapshot(window.location.search, document)
