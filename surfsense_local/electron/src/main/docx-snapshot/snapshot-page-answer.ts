/**
 * What the snapshot page's `window.docxSnapshot` resolved to, as the failure the
 * agent reads, or null once the pages are laid out. Anything but a string or null
 * means the page's script never set it: a missing bundle or a load error, which
 * only the window's console names.
 */
export function snapshotPageFailure(answer: unknown, consoleErrors: string[]): string | null {
  if (answer === null) return null
  if (typeof answer === "string") return answer
  const didNotStart = "the snapshot page did not start (its script did not load)"
  return consoleErrors.length > 0 ? `${didNotStart}: ${consoleErrors[0]}` : didNotStart
}
