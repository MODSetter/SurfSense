// Where reports go (contract 05, part B). A development build never sends
// unless SURFSENSE_TELEMETRY_DEV_ENDPOINT names a test server.
export const USAGE_ENDPOINT = "https://usage.surfsense.com/api/usage"

/** null: this build sends nothing. */
export function usageEndpoint(options: {
  packaged: boolean
  env: Record<string, string | undefined>
}): string | null {
  if (options.packaged) return USAGE_ENDPOINT
  const devEndpoint = options.env.SURFSENSE_TELEMETRY_DEV_ENDPOINT?.trim()
  if (!devEndpoint) return null
  try {
    const url = new URL(devEndpoint)
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null
  } catch {
    return null
  }
}
