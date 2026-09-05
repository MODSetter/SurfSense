import { ApiError, request, requestJson } from "@/lib/api"

import { parsePullStream, type PullProgress } from "./pull-stream"

export type Provider = {
  name: string
  healthy: boolean
  can_download: boolean
}

export type ProviderModel = {
  name: string
  installed: boolean
  capabilities: string[]
}

export type CatalogEntry = {
  name: string
  label: string
  size_gb: number
  installed: boolean
}

export type ModelSelection = {
  role: "generation"
  provider: string
  name: string
  updated_at: string
}

export type SelectableModel = ProviderModel & {
  provider: string
}

export function modelKey(model: Pick<SelectableModel, "provider" | "name">) {
  return `${model.provider}\0${model.name}`
}

export function getProviders(signal?: AbortSignal): Promise<Provider[]> {
  return requestJson<Provider[]>("/llm/providers", { signal })
}

export function getProviderModels(
  provider: string,
  signal?: AbortSignal
): Promise<ProviderModel[]> {
  return requestJson<ProviderModel[]>(
    `/llm/providers/${encodeURIComponent(provider)}/models`,
    { signal }
  )
}

export async function getGenerationSelection(
  signal?: AbortSignal
): Promise<ModelSelection | null> {
  try {
    return await requestJson<ModelSelection>("/llm/selection/generation", {
      signal,
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null
    }
    throw error
  }
}

export function setGenerationSelection(
  model: Pick<SelectableModel, "provider" | "name">,
  signal?: AbortSignal
): Promise<ModelSelection> {
  return requestJson<ModelSelection>("/llm/selection/generation", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: model.provider, name: model.name }),
    signal,
  })
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
