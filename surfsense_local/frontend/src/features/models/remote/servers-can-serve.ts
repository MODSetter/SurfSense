import type { ModelType } from "../model-type"

// Types no server model can fill yet. Every place that offers servers, in
// Settings and onboarding, asks here, so adding a type hides them everywhere.
const LOCAL_ONLY: ReadonlySet<ModelType> = new Set([
  // No server model can voice podcasts yet.
  "audio_gen",
])

export function serversCanServe(modelType: ModelType): boolean {
  return !LOCAL_ONLY.has(modelType)
}
