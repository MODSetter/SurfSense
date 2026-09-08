import { requestJson, requestVoid } from "@/lib/api"

export type DocumentStatus = "pending" | "processing" | "ready" | "failed"

export type WorkspaceDocument = {
  id: number
  title: string
  document_type: "FILE" | "NOTE"
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export type DocumentDetail = WorkspaceDocument & {
  content: string | null
}

export const SUPPORTED_SOURCE_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".pptx",
  ".xlsx",
  ".html",
  ".htm",
  ".csv",
  ".md",
  ".markdown",
  ".txt",
  ".text",
  ".png",
  ".jpg",
  ".jpeg",
  ".tif",
  ".tiff",
  ".bmp",
  ".webp",
] as const

export const SOURCE_FILE_ACCEPT = SUPPORTED_SOURCE_EXTENSIONS.join(",")

const supportedSourceExtensions = new Set<string>(SUPPORTED_SOURCE_EXTENSIONS)

export function isSupportedSourceFile(file: File): boolean {
  const dot = file.name.lastIndexOf(".")
  return (
    dot >= 0 &&
    supportedSourceExtensions.has(file.name.slice(dot).toLowerCase())
  )
}

export type UploadOutcome = {
  created: WorkspaceDocument[]
  duplicates: { filename: string; document_id: number }[]
  rejected: { filename: string; reason: string }[]
}

export function listDocuments(
  workspaceId: number,
  signal?: AbortSignal
): Promise<WorkspaceDocument[]> {
  return requestJson<WorkspaceDocument[]>(
    `/workspaces/${workspaceId}/documents?document_type=FILE&document_type=NOTE`,
    { signal }
  )
}

export function readDocument(
  workspaceId: number,
  documentId: number,
  signal?: AbortSignal
): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(
    `/workspaces/${workspaceId}/documents/${documentId}`,
    { signal }
  )
}

export function retryDocument(
  workspaceId: number,
  documentId: number,
  signal?: AbortSignal
): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(
    `/workspaces/${workspaceId}/documents/${documentId}/retry`,
    { method: "POST", signal }
  )
}

export function deleteDocument(
  workspaceId: number,
  documentId: number
): Promise<void> {
  return requestVoid(`/workspaces/${workspaceId}/documents/${documentId}`, {
    method: "DELETE",
  })
}

export function uploadDocuments(
  workspaceId: number,
  files: File[],
  signal?: AbortSignal
): Promise<UploadOutcome> {
  const body = new FormData()
  for (const file of files) {
    body.append("files", file)
  }
  return requestJson<UploadOutcome>(
    `/workspaces/${workspaceId}/documents/upload`,
    { method: "POST", body, signal }
  )
}
