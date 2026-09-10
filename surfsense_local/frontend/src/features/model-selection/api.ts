import { ApiError, request, requestJson, requestVoid } from "@/lib/api"

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
  role: "generation" | "image_generation"
  provider: string
  connection_id: number | null
  name: string
  updated_at: string
}

export type SelectableModel = ProviderModel & {
  provider: string
  connection_id: number | null
  connection_label?: string
  capability_known?: boolean
}

export type Connection = {
  id: number
  label: string
  provider: "openai_compatible"
  base_url: string
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export type ConnectionWrite = {
  label: string
  provider: "openai_compatible"
  base_url: string
  api_key?: string | null
  allow_unverified: boolean
}

export type ConnectionModel = {
  connection_id: number
  connection_label: string
  name: string
  capabilities: string[]
  capability_known: boolean
}

export type OnboardingStatus = {
  completed: boolean
}

export function modelKey(
  model: Pick<SelectableModel, "provider" | "connection_id" | "name">
) {
  return `${model.provider}\0${model.connection_id ?? ""}\0${model.name}`
}

export function getProviders(signal?: AbortSignal): Promise<Provider[]> {
  return requestJson<Provider[]>("/llm/providers", { signal })
}

export function getOnboardingStatus(
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", { signal })
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
            .map((model) => ({
              ...model,
              provider: provider.name,
              connection_id: null,
            }))
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

export async function getSelection(
  role: ModelSelection["role"],
  signal?: AbortSignal
): Promise<ModelSelection | null> {
  try {
    return await requestJson<ModelSelection>(`/llm/selection/${role}`, {
      signal,
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export function setGenerationSelection(
  model: Pick<SelectableModel, "provider" | "connection_id" | "name">,
  signal?: AbortSignal,
  allowUnlisted = false
): Promise<ModelSelection> {
  return setSelection("generation", model, signal, allowUnlisted)
}

export function setSelection(
  role: ModelSelection["role"],
  model: Pick<SelectableModel, "provider" | "connection_id" | "name">,
  signal?: AbortSignal,
  allowUnlisted = false
): Promise<ModelSelection> {
  return requestJson<ModelSelection>(`/llm/selection/${role}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: model.provider,
      connection_id: model.connection_id,
      name: model.name,
      allow_unlisted: allowUnlisted,
    }),
    signal,
  })
}

export function getConnections(signal?: AbortSignal): Promise<Connection[]> {
  return requestJson<Connection[]>("/llm/connections", { signal })
}

export function createConnection(
  body: ConnectionWrite,
  signal?: AbortSignal
): Promise<Connection> {
  return requestJson<Connection>("/llm/connections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
}

export function updateConnection(
  id: number,
  body: ConnectionWrite,
  signal?: AbortSignal
): Promise<Connection> {
  return requestJson<Connection>(`/llm/connections/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
}

export function deleteConnection(
  id: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/llm/connections/${id}`, { method: "DELETE", signal })
}

export function getConnectionModels(
  id: number,
  signal?: AbortSignal
): Promise<ConnectionModel[]> {
  return requestJson<ConnectionModel[]>(`/llm/connections/${id}/models`, {
    signal,
  })
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

export async function getAvailableGenerationModels(
  signal?: AbortSignal
): Promise<SelectableModel[]> {
  const [providers, connections] = await Promise.all([
    getProviders(signal),
    getConnections(signal).catch((error: unknown) => {
      if (signal?.aborted) throw error
      return []
    }),
  ])
  const [local, remote] = await Promise.all([
    getInstalledGenerationModels(providers, signal),
    Promise.all(
      connections.map(async (connection) => {
        try {
          const models = await getConnectionModels(connection.id, signal)
          return models
            .filter(
              (model) =>
                !model.capability_known ||
                model.capabilities.includes("completion")
            )
            .map((model) => ({
              ...model,
              provider: "openai_compatible",
              installed: true,
            }))
        } catch (error) {
          if (signal?.aborted) throw error
          return []
        }
      })
    ),
  ])
  return [...local, ...remote.flat()]
}
