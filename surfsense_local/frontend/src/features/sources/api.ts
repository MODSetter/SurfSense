import { apiUrl, requestJson, requestVoid } from "@/lib/api"

export type DocumentStatus =
  "pending" | "processing" | "ready" | "failed" | "cancelled"

export type WorkspaceDocument = {
  id: number
  title: string
  document_type: "FILE" | "NOTE"
  mime_type: string | null
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
  // Absent from an API without folders; null for a source outside any folder.
  folder_id?: number | null
}

// UX mirror of backend/modules/documents/storage.py UPLOAD_MIME_BY_SUFFIX.
// Update both when supported formats change; the backend remains authoritative.
// If formats become dynamic or change often, use a capabilities endpoint.
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
  // Per folder: the folder the same bytes already sit in.
  duplicates: {
    filename: string
    document_id: number
    folder_id?: number | null
  }[]
  rejected: { filename: string; reason: string }[]
}

export type DocumentChunk = {
  id: number
  content: string
  position: number
  start_line: number | null
  end_line: number | null
}

export type DocumentByChunk = {
  id: number
  title: string
  document_type: WorkspaceDocument["document_type"] | "ARTIFACT"
  workspace_id: number
  chunks: DocumentChunk[]
  total_chunks: number
  chunk_start_index: number
}

export function getDocumentByChunk(
  workspaceId: number,
  chunkId: number,
  signal?: AbortSignal
): Promise<DocumentByChunk> {
  return requestJson<DocumentByChunk>(
    `/workspaces/${workspaceId}/documents/by-chunk/${chunkId}?chunk_window=5`,
    { signal }
  )
}

// The API's largest page.
export const DOCUMENT_PAGE = 200

/** Every file and note, newest first, read page by page. */
export async function listDocuments(
  workspaceId: number,
  signal?: AbortSignal
): Promise<WorkspaceDocument[]> {
  const seen = new Map<number, WorkspaceDocument>()
  for (let offset = 0; ; offset += DOCUMENT_PAGE) {
    const page = await requestJson<WorkspaceDocument[]>(
      `/workspaces/${workspaceId}/documents?document_type=FILE&document_type=NOTE&limit=${DOCUMENT_PAGE}&offset=${offset}`,
      { signal }
    )
    // A source added meanwhile shifts the pages by one; the id keeps one copy.
    for (const document of page) {
      if (!seen.has(document.id)) seen.set(document.id, document)
    }
    if (page.length < DOCUMENT_PAGE) return [...seen.values()]
  }
}

export function originalDocumentUrl(
  workspaceId: number,
  documentId: number
): string {
  return apiUrl(`/workspaces/${workspaceId}/documents/${documentId}/original`)
}

export function retryDocument(
  workspaceId: number,
  documentId: number,
  signal?: AbortSignal
): Promise<WorkspaceDocument> {
  return requestJson<WorkspaceDocument>(
    `/workspaces/${workspaceId}/documents/${documentId}/retry`,
    { method: "POST", signal }
  )
}

export function cancelDocument(
  workspaceId: number,
  documentId: number,
  signal?: AbortSignal
): Promise<WorkspaceDocument> {
  return requestJson<WorkspaceDocument>(
    `/workspaces/${workspaceId}/documents/${documentId}/cancel`,
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
  signal?: AbortSignal,
  // Where the files go, and their paths under it when a folder was added.
  place?: { folderId?: number | null; relativePaths?: string[] | null }
): Promise<UploadOutcome> {
  const body = new FormData()
  for (const file of files) {
    body.append("files", file)
  }
  if (place?.folderId != null) {
    body.append("folder_id", String(place.folderId))
  }
  if (place?.relativePaths) {
    body.append("relative_paths", JSON.stringify(place.relativePaths))
  }
  return requestJson<UploadOutcome>(
    `/workspaces/${workspaceId}/documents/upload`,
    { method: "POST", body, signal }
  )
}

/** One document with its body: what the note editor reopens. */
export type DocumentWithContent = WorkspaceDocument & { content: string | null }

export function getDocument(
  workspaceId: number,
  documentId: number,
  signal?: AbortSignal
): Promise<DocumentWithContent> {
  return requestJson<DocumentWithContent>(
    `/workspaces/${workspaceId}/documents/${documentId}`,
    { signal }
  )
}

export function createNote(
  workspaceId: number,
  note: { title: string; content: string }
): Promise<WorkspaceDocument> {
  return requestJson<WorkspaceDocument>(
    `/workspaces/${workspaceId}/documents`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(note),
    }
  )
}

/** Unset fields are left alone; only a note takes `content`. */
export function updateDocument(
  workspaceId: number,
  documentId: number,
  changes: { title?: string; content?: string }
): Promise<WorkspaceDocument> {
  return requestJson<WorkspaceDocument>(
    `/workspaces/${workspaceId}/documents/${documentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }
  )
}
