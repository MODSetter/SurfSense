import { requestJson, requestVoid } from "@/lib/api"

export type ToolApproval = "ask" | "always"

export type PluginTool = {
  name: string
  title: string | null
  description: string
  annotations: Record<string, unknown>
  enabled: boolean
  approval: ToolApproval
}

export type Plugin = {
  id: string
  name: string
  source: "first_party" | "registry" | "custom"
  publisher: string
  url: string
  hosts: string[]
  enabled: boolean
  connected_at: string
  tools: PluginTool[]
}

export type CustomPluginWrite = { url: string; name: string; token?: string }

export const pluginsQueryKey = ["plugins"] as const
export const thirdPartyQueryKey = ["plugins", "third-party"] as const

const JSON_HEADERS = { "Content-Type": "application/json" }

export function listPlugins(signal?: AbortSignal): Promise<Plugin[]> {
  return requestJson<Plugin[]>("/plugins", { signal })
}

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
  change: { enabled: boolean } | { approval: ToolApproval }
): Promise<Plugin> {
  return requestJson<Plugin>(
    `/plugins/${id}/tools/${encodeURIComponent(tool)}`,
    { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(change) }
  )
}

export function disconnectPlugin(id: string): Promise<void> {
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
