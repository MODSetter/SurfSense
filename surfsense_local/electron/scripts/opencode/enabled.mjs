// Whether opencode, the agent's engine, is staged for dev runs and installers.
// On: every chat model may pick Agentic mode (docs/architecture/agent.md).
const ENABLED_BY_DEFAULT = true

/** Whether this build stages opencode: SURFSENSE_LOCAL_OPENCODE_ENABLED, 1 or 0, else the default. */
export function opencodeEnabled(env = process.env) {
  const value = env.SURFSENSE_LOCAL_OPENCODE_ENABLED
  return value === undefined ? ENABLED_BY_DEFAULT : value === "1"
}
