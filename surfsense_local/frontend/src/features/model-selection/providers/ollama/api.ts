import { request, requestJson } from "@/lib/api"

import { parsePullStream, type PullProgress } from "./pull-stream"

export type CatalogEntry = {
  name: string
  label: string
  size_gb: number
  installed: boolean
}

export function getProviderCatalog(
  provider: string,
  signal?: AbortSignal
): Promise<CatalogEntry[]> {
  return requestJson<CatalogEntry[]>(
    `/llm/providers/${encodeURIComponent(provider)}/catalog`,
    { signal }
  )
}

export async function pullModel(
  provider: string,
  name: string,
  onProgress: (progress: PullProgress) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await request(
    `/llm/providers/${encodeURIComponent(provider)}/pull`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
      signal,
    }
  )
  if (!response.body) {
    return
  }
  for await (const progress of parsePullStream(response.body)) {
    onProgress(progress)
  }
}
