/** Tracked changes as Word marks them, never told apart by colour alone:
 *  insertions underlined, deletions struck through. The page is always white,
 *  so the colours are fixed rather than themed. */
const TRACKED_CHANGES_CSS = `
ins { text-decoration-line: underline; color: #1d4ed8; }
del { text-decoration-line: line-through; color: #b91c1c; }
`

/** Add the tracked-changes rules to the element a Word file was laid out in. */
export function markTrackedChanges(container: HTMLElement): void {
  const style = container.ownerDocument.createElement("style")
  style.textContent = TRACKED_CHANGES_CSS
  container.append(style)
}
