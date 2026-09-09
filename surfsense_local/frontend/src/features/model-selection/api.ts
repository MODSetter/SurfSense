import { ApiError, requestJson } from "@/lib/api"

export type Provider = {
  name: string
  healthy: boolean
  can_download: boolean
  requires_key: boolean
  configured: boolean
}

export type ProviderModel = {
  name: string
  installed: boolean
  capabilities: string[]
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

export async function getInstalledGenerationModels(
  providers: Provider[],
  signal?: AbortSignal
): Promise<SelectableModel[]> {
  const modelGroups = await Promise.all(
    providers
      .filter((provider) => provider.healthy)
      .map(async (provider) => {
        try {
          const models = await getProviderModels(provider.name, signal)
          return models
            .filter(
              (model) =>
                model.installed && model.capabilities.includes("completion")
            )
            .map((model) => ({ ...model, provider: provider.name }))
        } catch (error) {
          if (signal?.aborted) {
            throw error
          }
          return []
        }
      })
  )
  return modelGroups
    .flat()
    .toSorted(
      (left, right) =>
        left.provider.localeCompare(right.provider) ||
        left.name.localeCompare(right.name)
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
