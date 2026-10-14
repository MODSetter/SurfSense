import type { WorkspaceDocument } from "./api"

function sameDocument(a: WorkspaceDocument, b: WorkspaceDocument) {
  const keys = Object.keys(a) as (keyof WorkspaceDocument)[]
  return (
    keys.length === Object.keys(b).length &&
    keys.every((key) => a[key] === b[key])
  )
}

/**
 * A re-read list holding the object each unchanged source already had, or the
 * current list itself when nothing changed, so a memoized row renders again
 * only for a source that did. Every 10 s while one ingests, and on each
 * workspace event, the whole list is read again.
 */
export function reuseUnchanged(
  current: WorkspaceDocument[],
  next: WorkspaceDocument[]
): WorkspaceDocument[] {
  const known = new Map(current.map((document) => [document.id, document]))
  let changed = current.length !== next.length
  const merged = next.map((document, index) => {
    const before = known.get(document.id)
    if (before === undefined || !sameDocument(before, document)) {
      changed = true
      return document
    }
    if (current[index] !== before) changed = true
    return before
  })
  return changed ? merged : current
}
