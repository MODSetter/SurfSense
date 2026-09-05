import { requestVoid } from "@/lib/api"

export function setProviderCredential(
  provider: string,
  apiKey: string,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(
    `/llm/providers/${encodeURIComponent(provider)}/credentials`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
      signal,
    }
  )
}

export function clearProviderCredential(
  provider: string,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(
    `/llm/providers/${encodeURIComponent(provider)}/credentials`,
    { method: "DELETE", signal }
  )
}
