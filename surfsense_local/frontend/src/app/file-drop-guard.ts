/**
 * Chromium opens a file dropped where nothing takes it, which in Electron
 * replaces the app with that file: the main process lets `file:` navigation
 * through. Refused at the window, a drop target that handles its own drop has
 * already claimed the event and is left alone.
 */
export function guardFileDrops(target: Window): () => void {
  const refuse = (event: Event) => {
    const transfer = (event as DragEvent).dataTransfer
    if (!transfer?.types.includes("Files") || event.defaultPrevented) return
    event.preventDefault()
    // The no-drop cursor, so a drop outside a target is visibly refused.
    transfer.dropEffect = "none"
  }
  target.addEventListener("dragover", refuse)
  target.addEventListener("drop", refuse)
  return () => {
    target.removeEventListener("dragover", refuse)
    target.removeEventListener("drop", refuse)
  }
}
