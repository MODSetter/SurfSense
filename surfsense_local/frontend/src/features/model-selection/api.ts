import { ApiError, request, requestJson, requestVoid } from "@/lib/api"

import type { ModelType } from "./model-type"

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
  display_name?: string | null
  types: ModelType[]
  /** The slots it can fill, by the one rule selection and every picker share. */
  selectable_for: ModelType[]
}

/**
 * Where a model's capabilities came from. "declared" is the endpoint's own word
 * for it, "catalog" the reviewed table shipped with the app. Nothing is guessed,
 * so an id neither source knows stays "unknown" and the picker says so.
 */
export type CapabilitySource = "declared" | "catalog" | "unknown"

export type ModelSelection = {
  model_type: ModelType
  provider: string
  connection_id: number | null
  name: string
  updated_at: string
}

export type SelectableModel = ProviderModel & {
  provider: string
  connection_id: number | null
  connection_label?: string
  capability_source?: CapabilitySource
}

export type Connection = {
  id: number
  label: string
  provider: "openai_compatible"
  base_url: string
  catalog_provider: string
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
  /** A remote manifest provider id, or "custom" for anything it does not list. */
  catalog_provider: string
}

/** The catalog provider of a connection the manifest does not list. */
export const CUSTOM_PROVIDER = "custom"

/** How a connection reaches a provider, from the remote manifest. */
export type ProviderConnect = {
  status: "ready" | "needs_account_details" | "needs_url" | "unreachable"
  base_url: string | null
  base_url_origin: "models.dev" | "reviewed" | null
  account_fields: { name: string; label: string }[]
  key: "required" | "none"
  local: boolean
  reason: string | null
}

export type RemoteProvider = {
  id: string
  name: string
  doc: string | null
  connect: ProviderConnect
  type_counts: Partial<Record<ModelType, number>>
  connections: number
}

export type ConnectionModel = {
  connection_id: number
  connection_label: string
  name: string
  types: ModelType[]
  capability_source: CapabilitySource
  /** The slots the backend says this model can fill; pickers never decide it. */
  selectable_for: ModelType[]
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

export function completeOnboarding(
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", {
    method: "POST",
    signal,
  })
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
                model.installed && model.selectable_for.includes("text_gen")
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
    return await requestJson<ModelSelection>("/llm/selection/text_gen", {
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
  modelType: ModelType,
  signal?: AbortSignal
): Promise<ModelSelection | null> {
  try {
    return await requestJson<ModelSelection>(`/llm/selection/${modelType}`, {
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
  return setSelection("text_gen", model, signal, allowUnlisted)
}

export function setSelection(
  modelType: ModelType,
  model: Pick<SelectableModel, "provider" | "connection_id" | "name">,
  signal?: AbortSignal,
  allowUnlisted = false
): Promise<ModelSelection> {
  return requestJson<ModelSelection>(`/llm/selection/${modelType}`, {
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

/** A connection's models that can fill the chat slot, as the backend decided. */
export function chatCandidates(models: ConnectionModel[]): SelectableModel[] {
  return models
    .filter((model) => model.selectable_for.includes("text_gen"))
    .map((model) => ({
      ...model,
      capabilities: model.types,
      provider: "openai_compatible",
      installed: true,
    }))
}

export function getRemoteProviders(
  signal?: AbortSignal
): Promise<RemoteProvider[]> {
  return requestJson<RemoteProvider[]>("/llm/catalog/remote", { signal })
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
          return chatCandidates(models)
        } catch (error) {
          if (signal?.aborted) throw error
          return []
        }
      })
    ),
  ])
  return [...local, ...remote.flat()]
}
