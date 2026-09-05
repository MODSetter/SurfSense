import { requestJson } from "@/lib/api"

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
