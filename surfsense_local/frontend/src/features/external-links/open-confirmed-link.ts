/** Opens a link the user confirmed: the desktop app's browser, or a new tab outside it. */
export function openConfirmedLink(url: string): void {
  if (window.surfsense?.openConfirmedLink) {
    void window.surfsense.openConfirmedLink(url)
    return
  }
  window.open(url, "_blank", "noopener,noreferrer")
}
