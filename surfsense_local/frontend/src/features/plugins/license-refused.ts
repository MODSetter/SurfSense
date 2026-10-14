import type { Plugin } from "./api"

// The plugin host's verdicts on the license, as the API's readiness reads them.
const REFUSED = new Set<Plugin["check_failure"]>([
  "needs_license",
  "license_expired",
  "license_revoked",
  "license_invalid",
])

/** Held out of `@` and the agent: a call would only be refused. */
export function licenseRefused(plugin: Plugin): boolean {
  return REFUSED.has(plugin.check_failure)
}
