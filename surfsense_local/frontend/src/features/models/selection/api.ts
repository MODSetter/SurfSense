import { ApiError, requestJson } from "@/lib/api"

import type { ModelType } from "../model-type"

export type ModelSelection = {
  model_type: ModelType
  provider: string
  connection_id: number | null
  name: string
  updated_at: string
}

/** What a selection write names: a model, and where it runs. */
export type SelectionTarget = Pick<
  ModelSelection,
  "provider" | "connection_id" | "name"
>

export function modelKey(model: SelectionTarget) {
  return `${model.provider}\0${model.connection_id ?? ""}\0${model.name}`
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

export function getGenerationSelection(signal?: AbortSignal) {
  return getSelection("text_gen", signal)
}

export function setSelection(
  modelType: ModelType,
  model: SelectionTarget,
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

export function setGenerationSelection(
  model: SelectionTarget,
  signal?: AbortSignal,
  allowUnlisted = false
): Promise<ModelSelection> {
  return setSelection("text_gen", model, signal, allowUnlisted)
}
