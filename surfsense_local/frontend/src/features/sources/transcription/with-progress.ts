import type { TranscriptionProgress, WorkspaceDocument } from "../api"

/**
 * Whether a window's progress event describes the rows as the list has them,
 * so it needs no re-read: every id known, transcribing, in the event's status.
 */
export function describesListed(
  documents: WorkspaceDocument[],
  ids: number[],
  status: string
): boolean {
  return ids.every((id) => {
    const document = documents.find((candidate) => candidate.id === id)
    return document?.status === status && Boolean(document.transcription)
  })
}

/** The list with these recordings' progress replaced; every other row kept. */
export function withProgress(
  documents: WorkspaceDocument[],
  ids: number[],
  progress: TranscriptionProgress
): WorkspaceDocument[] {
  return documents.map((document) =>
    ids.includes(document.id) && document.transcription
      ? {
          ...document,
          transcription: { ...document.transcription, progress },
        }
      : document
  )
}
