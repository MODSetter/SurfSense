import { apiUrl, requestJson, requestVoid } from "@/lib/api"

export type ToolApproval = "ask" | "always"

export type PluginTool = {
  name: string
  title: string | null
  description: string
  annotations: Record<string, unknown>
  enabled: boolean
  approval: ToolApproval
  /** Why it was switched off on its own, until the user allows it again. */
  change: "added" | "changed" | null
}

export type Plugin = {
  id: string
  name: string
  source: "first_party" | "registry" | "custom"
  publisher: string
  url: string
  hosts: string[]
  /** How it signs in; an `oauth` plugin signs in again rather than taking a new key. */
  auth_type: "none" | "token" | "license" | "oauth"
  enabled: boolean
  /** Disconnected by the user: kept with its tool settings, signed out, never offered. */
  disconnected: boolean
  connected_at: string
  /** When SurfSense last listed the server, and why that failed; null when it answered. */
  checked_at: string | null
  check_failure:
    | "unreachable"
    | "sign_in"
    | "needs_license"
    | "license_expired"
    | "license_revoked"
    | "license_invalid"
    | null
  /** Why the registry delisted it; its tools are no longer offered. */
  removed_reason: string | null
  tools: PluginTool[]
}

/** A sign-in under way: the page to open in the browser; the plugin is stored once it finishes. */
export type SignInStarted = {
  id: string
  plugin_id: string
  authorization_url: string
}

export type SignInProgress = {
  id: string
  plugin_id: string
  status: "waiting" | "connected" | "failed"
  message: string | null
}

/** A connect that answered with a sign-in to finish rather than a plugin. */
export function isSignInStarted(
  answer: Plugin | SignInStarted
): answer is SignInStarted {
  return "authorization_url" in answer
}

export type CustomPluginWrite = { url: string; name: string; token?: string }

/** One of SurfSense's own plugins, from the list packaged into the app. */
export type FirstPartyEntry = {
  id: string
  name: string
  description: string
  author: string
  /** `license` when it needs the SurfSense license. */
  access: "free" | "license"
  hosts: string[]
  connected: boolean
}

/** A partner's or community plugin, from the signed registry. */
export type RegistryEntry = {
  id: string
  name: string
  description: string
  author: string
  publisher: "partner" | "community"
  /** A partner's listing, reviewed as speaking for the company. */
  verified: boolean
  access: "free" | "external"
  /** What the user must have, when `access` is `external`. */
  access_note: string | null
  auth_type: "none" | "token" | "oauth"
  /** What key a `token` plugin asks for, in its publisher's words. */
  auth_title: string | null
  auth_description: string | null
  hosts: string[]
  homepage: string | null
  privacy_policy: string | null
  has_icon: boolean
  connected: boolean
}

export type Registry = {
  /** Nothing is fetched or listed while third-party plugins are off. */
  third_party_off: boolean
  fetched_at: string | null
  plugins: RegistryEntry[]
  removed: { id: string; reason: string }[]
}

export const pluginsQueryKey = ["plugins"] as const
export const thirdPartyQueryKey = ["plugins", "third-party"] as const
export const firstPartyQueryKey = ["plugins", "first-party"] as const
export const registryQueryKey = ["plugins", "registry"] as const

const JSON_HEADERS = { "Content-Type": "application/json" }

export function listPlugins(signal?: AbortSignal): Promise<Plugin[]> {
  return requestJson<Plugin[]>("/plugins", { signal })
}

export function listFirstParty(
  signal?: AbortSignal
): Promise<FirstPartyEntry[]> {
  return requestJson<FirstPartyEntry[]>("/plugins/first-party", { signal })
}

/** Connects even when the license is refused; the plugin's status says why. */
export function connectFirstParty(id: string): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/first-party/${id}`, { method: "POST" })
}

export function listRegistry(signal?: AbortSignal): Promise<Registry> {
  return requestJson<Registry>("/plugins/registry", { signal })
}

/** An `oauth` entry answers with a sign-in to finish in the browser. */
export function connectRegistryPlugin(
  id: string,
  token?: string
): Promise<Plugin | SignInStarted> {
  return requestJson<Plugin | SignInStarted>(
    `/plugins/registry/${id}`,
    token === undefined
      ? { method: "POST" }
      : {
          method: "POST",
          headers: JSON_HEADERS,
          body: JSON.stringify({ token }),
        }
  )
}

export function registryIconUrl(id: string): string {
  return apiUrl(`/plugins/registry/icons/${id}`)
}

/** A server asking for OAuth answers with a sign-in to finish in the browser. */
export function addCustomPlugin(
  write: CustomPluginWrite
): Promise<Plugin | SignInStarted> {
  return requestJson<Plugin | SignInStarted>("/plugins/custom", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(write),
  })
}

export function setPluginEnabled(
  id: string,
  enabled: boolean
): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ enabled }),
  })
}

export function setTool(
  id: string,
  tool: string,
  change: { enabled: boolean } | { approval: ToolApproval }
): Promise<Plugin> {
  return requestJson<Plugin>(
    `/plugins/${id}/tools/${encodeURIComponent(tool)}`,
    { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(change) }
  )
}

export function checkPlugin(id: string): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}/check`, { method: "POST" })
}

/** The server lists its tools with the new key first; a key it refuses is not saved. */
export function replacePluginKey(id: string, token: string): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}/key`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ token }),
  })
}

/** The same plugin signs in again, keeping its tool settings. */
export function signInAgain(id: string): Promise<SignInStarted> {
  return requestJson<SignInStarted>(`/plugins/${id}/sign-in`, {
    method: "POST",
  })
}

export function getPluginSignIn(
  id: string,
  signal?: AbortSignal
): Promise<SignInProgress> {
  return requestJson<SignInProgress>(`/plugins/sign-ins/${id}`, { signal })
}

export function cancelPluginSignIn(id: string): Promise<void> {
  return requestVoid(`/plugins/sign-ins/${id}`, { method: "DELETE" })
}

export function savePluginStep(
  threadId: number,
  stepId: string
): Promise<{ document_id: number }> {
  return requestJson<{ document_id: number }>(
    `/chat/threads/${threadId}/plugin-steps/${stepId}/save`,
    { method: "POST" }
  )
}

/** Drops the key or sign-in; the plugin stays, with its tool settings. */
export function disconnectPlugin(id: string): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}/disconnect`, { method: "POST" })
}

/** Connects a disconnected plugin that needs nothing entered; a key or a sign-in has its own call. */
export function connectPlugin(id: string): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}/connect`, { method: "POST" })
}

/** Deletes the plugin with its key and tool settings. */
export function removePlugin(id: string): Promise<void> {
  return requestVoid(`/plugins/${id}`, { method: "DELETE" })
}

export async function thirdPartyAllowed(
  signal?: AbortSignal
): Promise<boolean> {
  const { allowed } = await requestJson<{ allowed: boolean }>(
    "/plugins/third-party",
    { signal }
  )
  return allowed
}

export function setThirdPartyAllowed(allowed: boolean): Promise<void> {
  return requestVoid("/plugins/third-party", {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ allowed }),
  })
}
