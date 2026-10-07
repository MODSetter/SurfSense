// Whether opencode, the agent's engine, is staged for dev runs and installers.
// On: every installer carries the agent, and which model may run it is the
// API's to decide (docs/architecture/agent.md). 0 leaves it out of one build.
const ENABLED_BY_DEFAULT = true

/** Whether this build stages opencode: SURFSENSE_LOCAL_OPENCODE_ENABLED, 1 or 0, else the default. */
export function opencodeEnabled(env = process.env) {
  const value = env.SURFSENSE_LOCAL_OPENCODE_ENABLED
  return value === undefined ? ENABLED_BY_DEFAULT : value === "1"
}
