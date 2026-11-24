import { requestJson } from "@/lib/api"

export type SearchServer = {
  // Null while no server is named: search is off (ADR 0092).
  url: string | null
}

export const searchServerQueryKey = ["web-search", "server"] as const

export function readSearchServer(signal?: AbortSignal): Promise<SearchServer> {
  return requestJson<SearchServer>("/web-search/server", { signal })
}

/** Null turns search off. Contacts nothing: the next search asks. */
export function chooseSearchServer(url: string | null): Promise<SearchServer> {
  return requestJson<SearchServer>("/web-search/server", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
}
