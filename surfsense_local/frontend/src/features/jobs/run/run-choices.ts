import type { WorkspaceDocument } from "@/features/sources/api"

/** Whether a source is a file of the kind a run takes a copy of. */
export type FileKind = (document: WorkspaceDocument) => boolean

const isReading = (document: WorkspaceDocument) =>
  document.status === "pending" || document.status === "processing"

const newestFirst = (a: WorkspaceDocument, b: WorkspaceDocument) =>
  Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id

/** The ready files of a kind, newest first. */
export function readyFiles(
  documents: readonly WorkspaceDocument[],
  isKind: FileKind
): WorkspaceDocument[] {
  return documents
    .filter((document) => isKind(document) && document.status === "ready")
    .toSorted(newestFirst)
}

export function filesReading(
  documents: readonly WorkspaceDocument[],
  isKind: FileKind
): number {
  return documents.filter((document) => isKind(document) && isReading(document))
    .length
}

/** The newest file ticked in the sidebar, else the newest; null when there is none. */
export function newestTicked(
  choices: readonly WorkspaceDocument[],
  includedIds: readonly number[]
): number | null {
  const ticked = choices.find((choice) => includedIds.includes(choice.id))
  return (ticked ?? choices[0])?.id ?? null
}

/** Every ready source but the file the run copies, which is never its own evidence. */
export function otherReadySources(
  documents: readonly WorkspaceDocument[],
  fileId: number | null
): WorkspaceDocument[] {
  return documents.filter(
    (document) => document.status === "ready" && document.id !== fileId
  )
}

/** Sources of other kinds still being read; the file's own kind is counted apart. */
export function otherSourcesReading(
  documents: readonly WorkspaceDocument[],
  isKind: FileKind
): number {
  return documents.filter(
    (document) => !isKind(document) && isReading(document)
  ).length
}
