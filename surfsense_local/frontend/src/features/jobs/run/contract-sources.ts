import type { WorkspaceDocument } from "@/features/sources/api"

import {
  filesReading,
  newestTicked,
  otherReadySources,
  otherSourcesReading,
  readyFiles,
} from "./run-choices"

// The stored type of an uploaded .docx (the backend's UPLOAD_MIME_BY_SUFFIX),
// so a renamed file still counts. A .doc is no source a redline can mark up.
export const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

export function isContract(document: WorkspaceDocument): boolean {
  return document.document_type === "FILE" && document.mime_type === DOCX_MIME
}

export function contractChoices(
  documents: readonly WorkspaceDocument[]
): WorkspaceDocument[] {
  return readyFiles(documents, isContract)
}

export function contractsReading(
  documents: readonly WorkspaceDocument[]
): number {
  return filesReading(documents, isContract)
}

/** The newest contract ticked in the sidebar, else the newest; null when there is none. */
export const defaultContract = newestTicked

/** Every ready source but the contract, which is never its own playbook. */
export const playbookChoices = otherReadySources

export function playbookReading(
  documents: readonly WorkspaceDocument[]
): number {
  return otherSourcesReading(documents, isContract)
}

/** A source the user ticked or unticked here keeps that. Any other starts as
 *  the sidebar has it, another Word file too: it may be the firm's own
 *  standard agreement. */
export function chosenPlaybook(
  choices: readonly WorkspaceDocument[],
  marks: ReadonlyMap<number, boolean>,
  includedIds: readonly number[]
): number[] {
  return choices
    .filter((choice) => marks.get(choice.id) ?? includedIds.includes(choice.id))
    .map((choice) => choice.id)
}
