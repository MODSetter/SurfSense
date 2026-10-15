import { ApiError, requestJson, requestVoid } from "@/lib/api"

/** One folder. A root's own folder has no parent and is never shown as a row. */
export type SourceFolder = {
  id: number
  parent_id: number | null
  // The source root it belongs to; only the Library exists for now.
  root_id?: number
  name: string
  role?: "evidence" | "target" | "playbook" | "library" | null
}

export type DocumentMoveOutcome = {
  moved: number[]
  // Left where they were: the target folder already holds the same bytes.
  skipped: { document_id: number; reason: "duplicate"; duplicate_of: number }[]
}

const json = { "Content-Type": "application/json" }

/** Every folder of the workspace; none when the API has no folders yet. */
export async function listFolders(
  workspaceId: number,
  signal?: AbortSignal
): Promise<SourceFolder[]> {
  try {
    return await requestJson<SourceFolder[]>(
      `/workspaces/${workspaceId}/folders`,
      { signal }
    )
  } catch (cause) {
    // An API without folders answers 404, and its workspace is one flat list.
    if (cause instanceof ApiError && cause.status === 404) return []
    throw cause
  }
}

export function createFolder(
  workspaceId: number,
  folder: { parent_id: number | null; name: string }
): Promise<SourceFolder> {
  return requestJson<SourceFolder>(`/workspaces/${workspaceId}/folders`, {
    method: "POST",
    headers: json,
    body: JSON.stringify(folder),
  })
}

/** Renames and/or moves; unset fields are left alone. */
export function updateFolder(
  workspaceId: number,
  folderId: number,
  changes: { name?: string; parent_id?: number }
): Promise<SourceFolder> {
  return requestJson<SourceFolder>(
    `/workspaces/${workspaceId}/folders/${folderId}`,
    { method: "PATCH", headers: json, body: JSON.stringify(changes) }
  )
}

/** What deleting a folder removes, counted on the server. */
export type FolderSummary = {
  folders: number
  // Files and notes anywhere below it.
  sources: number
  // Studio outputs filed below it, which the tree does not list.
  artifacts: number
}

export function getFolderSummary(
  workspaceId: number,
  folderId: number
): Promise<FolderSummary> {
  return requestJson<FolderSummary>(
    `/workspaces/${workspaceId}/folders/${folderId}/summary`
  )
}

/** Deletes the folder, everything under it, and their sources, for good. */
export function deleteFolder(
  workspaceId: number,
  folderId: number
): Promise<void> {
  return requestVoid(`/workspaces/${workspaceId}/folders/${folderId}`, {
    method: "DELETE",
  })
}

export function moveDocuments(
  workspaceId: number,
  documentIds: number[],
  folderId: number
): Promise<DocumentMoveOutcome> {
  return requestJson<DocumentMoveOutcome>(
    `/workspaces/${workspaceId}/documents/move`,
    {
      method: "POST",
      headers: json,
      body: JSON.stringify({ document_ids: documentIds, folder_id: folderId }),
    }
  )
}
