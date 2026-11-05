import { requestJson } from "@/lib/api"

export type SearchServer = {
  // Null while searches go to SurfSense's server, `default_url`.
  url: string | null
  default_url: string
}

export const searchServerQueryKey = ["web-search", "server"] as const

export function readSearchServer(signal?: AbortSignal): Promise<SearchServer> {
  return requestJson<SearchServer>("/web-search/server", { signal })
}

/** Null goes back to SurfSense's server. Contacts nothing: the next search asks. */
export function chooseSearchServer(url: string | null): Promise<SearchServer> {
  return requestJson<SearchServer>("/web-search/server", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
}
