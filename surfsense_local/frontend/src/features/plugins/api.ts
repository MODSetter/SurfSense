import { apiUrl, requestJson, requestVoid } from "@/lib/api"

export type ToolApproval = "ask" | "always"

/** One write can switch a tool on and set how it asks, so a pick is never half applied. */
export type ToolChange = { enabled?: boolean; approval?: ToolApproval }

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
  url: string
  hosts: string[]
  /** How it signs in; an `oauth` plugin signs in again rather than taking a new key. */
  auth_type: "none" | "token" | "headers" | "license" | "oauth"
  /** A `headers` plugin's header names; their values never come back from the API. */
  header_names: string[]
  /** `sse` for a plugin added on the older HTTP+SSE transport, which no engine speaks:
   * it stays until the user replaces it with its Streamable HTTP address. */
  transport: "streamable_http" | "sse"
  /** Scopes the server's `insufficient_scope` asked for; Sign in asks for them. */
  needs_scopes: string[]
  // Signs in with the user's own OAuth app, which they may change.
  own_app: boolean
  // Needs the user's own app to sign in: the provider registers no app, or refused SurfSense.
  needs_own_app: "needs_client" | "refused" | null
  /** An OAuth plugin saved before its first sign-in: it connects, rather than signs in again. */
  never_signed_in: boolean
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
  /** Why it failed: a code the screen has words for, and the API's sentence; null otherwise. */
  code: string | null
  message: string | null
  /** The host not allowed, or the name the server is connected as, for the screen's sentence. */
  host: string | null
  name: string | null
}

/** A connect that answered with a sign-in to finish rather than a plugin. */
export function isSignInStarted(
  answer: Plugin | SignInStarted
): answer is SignInStarted {
  return "authorization_url" in answer
}

/** One header a plugin's server reads, such as its key in `x-api-key`. */
export type SignInHeader = { name: string; value: string }

/** The user's own OAuth app, for a provider taking only apps registered in advance. */
export type OwnApp = {
  client_id: string
  client_secret?: string
  scopes?: string[]
}

/** A bare `token` is sent as `Authorization: Bearer`; `headers` send a key any other way. */
export type CustomPluginWrite = {
  url: string
  name: string
  token?: string
  headers?: SignInHeader[]
}

/** One of SurfSense's own plugins, from the list packaged into the app. */
export type FirstPartyEntry = {
  id: string
  name: string
  description: string
  author: string
  /** `license` when it needs the SurfSense license. */
  access: "free" | "license"
  hosts: string[]
  /** What its public page says of it; its card shows `description`. */
  about: string
  tools: string[]
  /** `YYYY-MM`, the month it joined the list. */
  added: string
  has_icon: boolean
  connected: boolean
}

/** A third-party plugin from the signed registry, verified or community. */
export type RegistryEntry = {
  id: string
  name: string
  description: string
  author: string
  verification: "verified" | "community"
  /** A maintainer judged that its author runs the server that receives its calls. */
  verified: boolean
  access: "free" | "external"
  /** What the user must have, when `access` is `external`. */
  access_note: string | null
  auth_type: "none" | "token" | "headers" | "oauth"
  /** What key a `token` plugin asks for, in its publisher's words. */
  auth_title: string | null
  auth_description: string | null
  /** The headers a `headers` plugin's key goes in, each worded by its entry. */
  auth_headers: {
    name: string
    label: string | null
    description: string | null
  }[]
  /** An `oauth` plugin whose provider takes only apps registered in advance. */
  user_client: boolean
  hosts: string[]
  /** The host every call goes to; an OAuth plugin's other hosts see only the sign-in. */
  server_host: string
  sign_in_hosts: string[]
  homepage: string | null
  privacy_policy: string | null
  /** What its page shows before it is connected; `tools` is null when the entry lists none. */
  about: string | null
  tools: string[] | null
  /** `YYYY-MM`, the month it joined the registry; null in an older entry. */
  added: string | null
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
/** A key, each named header's value, or the user's own app, as the entry asks. */
export type RegistryConnectWrite =
  { token: string } | { headers: SignInHeader[] } | { oauth_client: OwnApp }

export function connectRegistryPlugin(
  id: string,
  write?: RegistryConnectWrite
): Promise<Plugin | SignInStarted> {
  return requestJson<Plugin | SignInStarted>(
    `/plugins/registry/${id}`,
    write === undefined
      ? { method: "POST" }
      : { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(write) }
  )
}

export function registryIconUrl(id: string): string {
  return apiUrl(`/plugins/registry/icons/${id}`)
}

/** Packaged with the app beside SurfSense's list, so it needs no network. */
export function firstPartyIconUrl(id: string): string {
  return apiUrl(`/plugins/first-party/icons/${id}`)
}

/** A server asking for OAuth answers with a sign-in to finish in the browser. */
export function addCustomPlugin(write: CustomPluginWrite): Promise<Plugin> {
  return requestJson<Plugin>("/plugins/custom", {
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
  change: ToolChange
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
/** The server lists its tools with the new headers first; ones it refuses are not saved. */
export function replacePluginHeaders(
  id: string,
  headers: SignInHeader[]
): Promise<Plugin> {
  return requestJson<Plugin>(`/plugins/${id}/headers`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ headers }),
  })
}

/** With `oauthClient`, signs in as the user's own app from then on. */
export function signInAgain(
  id: string,
  oauthClient?: OwnApp
): Promise<SignInStarted> {
  return requestJson<SignInStarted>(`/plugins/${id}/sign-in`, {
    method: "POST",
    ...(oauthClient
      ? {
          headers: JSON_HEADERS,
          body: JSON.stringify({ oauth_client: oauthClient }),
        }
      : {}),
  })
}

/** The callback a user registers their own OAuth app with, for this build. */
export async function oauthRedirectUri(): Promise<string> {
  const answer = await requestJson<{ redirect_uri: string }>(
    "/plugins/oauth/redirect-uri"
  )
  return answer.redirect_uri
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
