/** What the ladder measured of a model; `not_measured` keeps today's behaviour. */
export type CapabilityLevel =
  "agent" | "agent_limited" | "studio_only" | "not_measured"

/** How a chat answers, chosen when it starts and kept. */
export type ChatMode = "basic" | "agentic"

/** Why the level is what it is, as a code the catalogs word. */
export type CapabilityReason = {
  code: string
  values: Record<string, string | number>
}

/** The row the level was read from, for the evidence line. */
export type MeasuredRow = {
  key: string
  // `create-and-edit`, `openrouter-screen`, or `assumed` for a flagship not run.
  suite: string
  assumed: boolean
  suite_version: number
  measured_on: string
  provider: string
  host: string
  reads_images: boolean
  passed: number
  counted: number
  provisional: boolean
}

/** What a new chat on the model may be. A score never blocks Agentic. */
export type ChatModes = {
  agentic_allowed: boolean
  /** `agent_not_installed`, `tool_calls_unsupported` or `window_below_floor`. */
  blocked: string | null
  default_mode: ChatMode
  /**
   * What the switch says beside Agentic: `measured_pass`, `measured_near` or
   * `measured_below` with `passed` and `counted`; `local_copy` with `host`;
   * `assumed`; `untested`.
   */
  reason: CapabilityReason
  remembered_mode: ChatMode | null
}

export type ModelCapability = {
  level: CapabilityLevel
  label_key: CapabilityLevel
  reason: CapabilityReason
  /** English, from the list the app ships; a model's description. */
  note: string | null
  measured: MeasuredRow | null
  modes: ChatModes
}
