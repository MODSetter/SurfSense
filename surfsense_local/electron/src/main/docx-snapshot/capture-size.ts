// The API cuts a capture into screens of 1,000 px and keeps four
// (backend previews/page_screens.py), so nothing taller is worth capturing.
export const CAPTURE_WIDTH = 1280
const SCREEN = 1000
const SCREENS = 4

/** How tall to capture a page that says it is `scrolled` px tall; the page's own answer is not trusted. */
export function captureHeight(scrolled: unknown): number {
  if (typeof scrolled !== "number" || !Number.isFinite(scrolled)) return SCREEN
  return Math.min(SCREEN * SCREENS, Math.max(SCREEN, Math.ceil(scrolled)))
}
