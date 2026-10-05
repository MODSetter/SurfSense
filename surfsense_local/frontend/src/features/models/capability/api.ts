import { requestJson } from "@/lib/api"

/** What the ladder measured of a model; `not_measured` keeps today's behaviour. */
export type CapabilityLevel =
  "agent" | "agent_limited" | "studio_only" | "not_measured"

/** Why the level is what it is, as a code the catalogs word. */
export type CapabilityReason = {
  code: string
  values: Record<string, string | number>
}

/** The row the level was read from, for the evidence line. */
export type MeasuredRow = {
  key: string
  suite_version: number
  measured_on: string
  provider: string
  host: string
  reads_images: boolean
  passed: number
  counted: number
  provisional: boolean
}

export type AgentTrial = {
  offered: boolean
  enabled: boolean
  /** `tool_calls_unconfirmed` or `window_below_floor` when not offered. */
  blocked: string | null
}

export type ModelCapability = {
  level: CapabilityLevel
  label_key: CapabilityLevel
  reason: CapabilityReason
  /** English, from the list the app ships; a model's description. */
  note: string | null
  measured: MeasuredRow | null
  agent_trial: AgentTrial
}

export function setAgentTrial(
  enabled: boolean,
  signal?: AbortSignal
): Promise<ModelCapability> {
  return requestJson<ModelCapability>("/llm/selection/text_gen/agent-trial", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
    signal,
  })
}
