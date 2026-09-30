import { request, requestJson, requestVoid } from "@/lib/api"

import { parseWorkspaceEvents, type WorkspaceEvent } from "./read-sse"

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

/**
 * `connected` once the API is listening for this client, then one event per
 * change, until the stream ends or `signal` aborts. An event says that rows
 * changed, never what they became: the caller reloads.
 */
export async function* followWorkspaceEvents(
  workspaceId: number,
  signal: AbortSignal
): AsyncGenerator<WorkspaceEvent> {
  const response = await request(`/workspaces/${workspaceId}/events`, {
    signal,
  })
  if (!response.body) return
  yield* parseWorkspaceEvents(response.body)
}
