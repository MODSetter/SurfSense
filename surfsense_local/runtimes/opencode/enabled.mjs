// Whether opencode, the agent's engine, is staged for dev runs and installers.
// On: every installer carries the agent, and which model may run it is the
// API's to decide (docs/architecture/agent.md). 0 leaves it out of one build.
const ENABLED_BY_DEFAULT = true

/** Whether this build stages opencode: SURFSENSE_LOCAL_OPENCODE_ENABLED, 1 or 0, unset or empty for the default. */
export function opencodeEnabled(env = process.env) {
  const value = env.SURFSENSE_LOCAL_OPENCODE_ENABLED
  if (value === undefined || value === "") return ENABLED_BY_DEFAULT
  if (value === "1") return true
  if (value === "0") return false
  // "true" or "no" could be read either way, and off silently ships an installer without the agent.
  throw new Error(`SURFSENSE_LOCAL_OPENCODE_ENABLED is "${value}"; set it to 1 or 0, or leave it unset`)
}
