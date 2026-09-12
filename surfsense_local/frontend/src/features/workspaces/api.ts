import { requestJson, requestVoid } from "@/lib/api"

export type Workspace = {
  id: number
  name: string
  created_at: string
  updated_at: string
}

export function listWorkspaces(signal?: AbortSignal): Promise<Workspace[]> {
  return requestJson<Workspace[]>("/workspaces", { signal })
}

export function createWorkspace(
  name: string,
  signal?: AbortSignal
): Promise<Workspace> {
  return requestJson<Workspace>("/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    signal,
  })
}

export function renameWorkspace(
  id: number,
  name: string,
  signal?: AbortSignal
): Promise<Workspace> {
  return requestJson<Workspace>(`/workspaces/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    signal,
  })
}

export function deleteWorkspace(
  id: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/workspaces/${id}`, { method: "DELETE", signal })
}
