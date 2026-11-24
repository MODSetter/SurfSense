import { requestJson } from "@/lib/api"

import type { ModelType } from "../../../model-type"
import type { Connection } from "../api"

/** Whether a slot offers ElevenLabs, decided by the backend. */
export type ElevenLabsOptionRead = { serves: ModelType[] }

export const elevenLabsOptionQueryKey = ["elevenlabs-option"] as const

export function getElevenLabsOption(
  signal?: AbortSignal
): Promise<ElevenLabsOptionRead> {
  return requestJson<ElevenLabsOptionRead>("/llm/connections/elevenlabs", {
    signal,
  })
}

/** Saved only once ElevenLabs accepts the key; its address is not the user's. */
export function connectElevenLabs(body: {
  label: string
  api_key: string
}): Promise<Connection> {
  return requestJson<Connection>("/llm/connections/elevenlabs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
