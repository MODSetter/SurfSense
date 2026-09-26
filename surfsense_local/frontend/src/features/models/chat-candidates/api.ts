import { requestJson } from "@/lib/api"

import type { ModelType } from "../model-type"
import { getConnections } from "../remote/connections/api"
import {
  getConnectionModels,
  type CapabilitySource,
  type ConnectionModel,
} from "../remote/models/api"

/** A local runtime the backend runs, such as llama.cpp. */
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

/** A model that can fill the chat slot right now, from any source. */
export type SelectableModel = ProviderModel & {
  provider: string
  connection_id: number | null
  connection_label?: string
  capability_source?: CapabilitySource
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

async function getInstalledGenerationModels(
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
