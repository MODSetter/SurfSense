import { request, requestJson } from "@/lib/api"

import type { ModelType } from "../../model-type"

/**
 * Where a model's capabilities came from. "declared" is the endpoint's own word
 * for it, "catalog" the reviewed table shipped with the app. Nothing is guessed,
 * so an id neither source knows stays "unknown" and the picker says so.
 */
export type CapabilitySource = "declared" | "catalog" | "unknown"

export type ConnectionModel = {
  connection_id: number
  connection_label: string
  name: string
  types: ModelType[]
  capability_source: CapabilitySource
  /** The slots the backend says this model can fill; pickers never decide it. */
  selectable_for: ModelType[]
}

export function getConnectionModels(
  id: number,
  signal?: AbortSignal
): Promise<ConnectionModel[]> {
  return requestJson<ConnectionModel[]>(`/llm/connections/${id}/models`, {
    signal,
  })
}

export async function testConnectionChat(
  id: number,
  model: string,
  signal?: AbortSignal
): Promise<string> {
  const { reply } = await requestJson<{ reply: string }>(
    `/llm/connections/${id}/chat-test`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
      signal,
    }
  )
  return reply
}

export async function testConnectionImage(
  id: number,
  model: string,
  signal?: AbortSignal
): Promise<Blob> {
  const response = await request(`/llm/connections/${id}/image-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
    signal,
  })
  return response.blob()
}
