import type { DocumentTranscription, WorkspaceDocument } from "./api"

// The one nested field: every re-read parses it into a new object.
function sameTranscription(
  a: DocumentTranscription | null | undefined,
  b: DocumentTranscription | null | undefined
) {
  if (a === b) return true
  if (!a || !b) return false
  return (
    a.language === b.language &&
    a.awaiting === b.awaiting &&
    (a.progress === b.progress ||
      (a.progress !== null &&
        b.progress !== null &&
        a.progress.done_s === b.progress.done_s &&
        a.progress.total_s === b.progress.total_s))
  )
}

function sameDocument(a: WorkspaceDocument, b: WorkspaceDocument) {
  const keys = Object.keys(a) as (keyof WorkspaceDocument)[]
  return (
    keys.length === Object.keys(b).length &&
    keys.every((key) =>
      key === "transcription"
        ? key in b && sameTranscription(a.transcription, b.transcription)
        : a[key] === b[key]
    )
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
