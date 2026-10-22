// A frame inside the app's window shows content the app does not trust: a page
// the model wrote, or a Word file. Its sandbox stops it reaching the app, but a
// sandboxed frame may still navigate itself, and the URL it goes to can carry
// what it read off the machine (ADR 0066). It may only load what the app gave it.
const FRAME_PAGES = new Set(["about:srcdoc", "about:blank"])

/** Whether a frame below the window's own page may navigate to `url`. */
export function frameMayNavigate(url: string): boolean {
  return FRAME_PAGES.has(url)
}
