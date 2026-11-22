import type { WorkspaceDocument } from "@/features/sources/api"

import {
  filesReading,
  newestTicked,
  otherReadySources,
  otherSourcesReading,
  readyFiles,
} from "./run-choices"

// The stored type of an uploaded .xlsx (the backend's UPLOAD_MIME_BY_SUFFIX),
// so a renamed file still counts. An .xlsm is no source yet.
export const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

export function isWorkbook(document: WorkspaceDocument): boolean {
  return document.document_type === "FILE" && document.mime_type === XLSX_MIME
}

export function workbookChoices(
  documents: readonly WorkspaceDocument[]
): WorkspaceDocument[] {
  return readyFiles(documents, isWorkbook)
}

export function workbooksReading(
  documents: readonly WorkspaceDocument[]
): number {
  return filesReading(documents, isWorkbook)
}

/** The newest workbook ticked in the sidebar, else the newest; null when there is none. */
export const defaultWorkbook = newestTicked

export const policyChoices = otherReadySources

export function sourcesReading(
  documents: readonly WorkspaceDocument[]
): number {
  return otherSourcesReading(documents, isWorkbook)
}

/** A source the user ticked or unticked here keeps that. Any other starts as
 *  the sidebar has it, except another workbook: one questionnaire is rarely
 *  the evidence for another. */
export function chosenPolicies(
  choices: readonly WorkspaceDocument[],
  marks: ReadonlyMap<number, boolean>,
  includedIds: readonly number[]
): number[] {
  return choices
    .filter(
      (choice) =>
        marks.get(choice.id) ??
        (includedIds.includes(choice.id) && !isWorkbook(choice))
    )
    .map((choice) => choice.id)
}
