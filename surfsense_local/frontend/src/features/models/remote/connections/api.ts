import { requestJson, requestVoid } from "@/lib/api"

import type { ModelType } from "../../model-type"

export type Connection = {
  id: number
  label: string
  provider: "openai_compatible"
  base_url: string
  catalog_provider: string
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export type ConnectionWrite = {
  label: string
  provider: "openai_compatible"
  base_url: string
  api_key?: string | null
  allow_unverified: boolean
  /** A remote manifest provider id, or "custom" for anything it does not list. */
  catalog_provider: string
}

/** The catalog provider of a connection the manifest does not list. */
export const CUSTOM_PROVIDER = "custom"

/** How a connection reaches a provider, from the remote manifest. */
export type ProviderConnect = {
  status: "ready" | "needs_account_details" | "needs_url" | "unreachable"
  base_url: string | null
  base_url_origin: "models.dev" | "reviewed" | null
  account_fields: { name: string; label: string }[]
  key: "required" | "none"
  local: boolean
  reason: string | null
}

export type RemoteProvider = {
  id: string
  name: string
  doc: string | null
  connect: ProviderConnect
  type_counts: Partial<Record<ModelType, number>>
  connections: number
}

export function getRemoteProviders(
  signal?: AbortSignal
): Promise<RemoteProvider[]> {
  return requestJson<RemoteProvider[]>("/llm/catalog/remote", { signal })
}

export function getConnections(signal?: AbortSignal): Promise<Connection[]> {
  return requestJson<Connection[]>("/llm/connections", { signal })
}

export function createConnection(
  body: ConnectionWrite,
  signal?: AbortSignal
): Promise<Connection> {
  return requestJson<Connection>("/llm/connections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
}

export function updateConnection(
  id: number,
  body: ConnectionWrite,
  signal?: AbortSignal
): Promise<Connection> {
  return requestJson<Connection>(`/llm/connections/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
}

export function deleteConnection(
  id: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/llm/connections/${id}`, { method: "DELETE", signal })
}
