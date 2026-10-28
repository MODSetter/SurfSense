import { intl } from "@/i18n/intl"
import { getHealth } from "@/lib/api"

import { uploadDocuments, type UploadOutcome } from "../api"
import type { UploadBatch } from "./upload-plan"

// fetch's own failure: no answer came. Either the API is down, or Chromium
// could not read one of the files, which fails the whole request: a file
// another app holds open, or one moved since it was picked.
function isUnanswered(error: unknown) {
  return error instanceof TypeError
}

async function apiAnswers(signal: AbortSignal) {
  try {
    await getHealth(signal)
    return true
  } catch (cause) {
    if (signal.aborted) throw cause
    return !isUnanswered(cause)
  }
}

/**
 * One request of an upload. One that got no answer goes again a file at a
 * time, so a file Chromium cannot read is listed as rejected and the rest
 * still arrive; when the API itself is not answering, the first error stands.
 * A file the API refuses then is listed with its reason, since the files sent
 * before it are already in.
 */
export async function sendBatch(
  workspaceId: number,
  batch: UploadBatch,
  signal: AbortSignal,
  folderId: number | null
): Promise<UploadOutcome> {
  try {
    return await uploadDocuments(workspaceId, batch.files, signal, {
      folderId,
      relativePaths: batch.relativePaths,
    })
  } catch (cause) {
    if (!isUnanswered(cause)) throw cause
    const outcome: UploadOutcome = { created: [], duplicates: [], rejected: [] }
    const unread: string[] = []
    for (const [index, file] of batch.files.entries()) {
      try {
        const answered = await uploadDocuments(workspaceId, [file], signal, {
          folderId,
          relativePaths: batch.relativePaths && [batch.relativePaths[index]],
        })
        outcome.created.push(...answered.created)
        outcome.duplicates.push(...answered.duplicates)
        outcome.rejected.push(...answered.rejected)
      } catch (single) {
        if (signal.aborted) throw single
        if (isUnanswered(single)) {
          unread.push(file.name)
        } else {
          outcome.rejected.push({
            filename: file.name,
            reason: single instanceof Error ? single.message : String(single),
          })
        }
      }
    }
    // Asked even when some arrived: the API may have stopped partway.
    if (unread.length > 0 && !(await apiAnswers(signal))) throw cause
    outcome.rejected.push(
      ...unread.map((filename) => ({
        filename,
        reason: intl.formatMessage({
          id: "sources_upload_unreadable_reason_label",
          defaultMessage: "Couldn’t be read; it may be open in another app",
        }),
      }))
    )
    return outcome
  }
}
