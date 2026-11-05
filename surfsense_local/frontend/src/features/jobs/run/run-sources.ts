import type { WorkspaceDocument } from "@/features/sources/api"

// The stored type of an uploaded .xlsx (the backend's UPLOAD_MIME_BY_SUFFIX),
// so a renamed file still counts. An .xlsm is no source yet.
export const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

export function isWorkbook(document: WorkspaceDocument): boolean {
  return document.document_type === "FILE" && document.mime_type === XLSX_MIME
}

const isReading = (document: WorkspaceDocument) =>
  document.status === "pending" || document.status === "processing"

const newestFirst = (a: WorkspaceDocument, b: WorkspaceDocument) =>
  Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id

export function workbookChoices(
  documents: readonly WorkspaceDocument[]
): WorkspaceDocument[] {
  return documents
    .filter((document) => isWorkbook(document) && document.status === "ready")
    .toSorted(newestFirst)
}

export function workbooksReading(
  documents: readonly WorkspaceDocument[]
): number {
  return documents.filter(
    (document) => isWorkbook(document) && isReading(document)
  ).length
}

/** The newest workbook ticked in the sidebar, else the newest; null when there is none. */
export function defaultWorkbook(
  choices: readonly WorkspaceDocument[],
  includedIds: readonly number[]
): number | null {
  const ticked = choices.find((choice) => includedIds.includes(choice.id))
  return (ticked ?? choices[0])?.id ?? null
}

export function policyChoices(
  documents: readonly WorkspaceDocument[],
  workbookId: number | null
): WorkspaceDocument[] {
  return documents.filter(
    (document) => document.status === "ready" && document.id !== workbookId
  )
}

export function sourcesReading(
  documents: readonly WorkspaceDocument[]
): number {
  return documents.filter(
    (document) => !isWorkbook(document) && isReading(document)
  ).length
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
