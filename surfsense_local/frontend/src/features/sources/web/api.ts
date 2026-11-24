import { requestJson } from "@/lib/api"

import type { WorkspaceDocument } from "../api"

export type WebResult = {
  url: string
  title: string
  description: string | null
  site: string
  // What would read it: "youtube" for a video's transcript, "web_page" for a page.
  puller: string
}

export type WebResults = {
  results: WebResult[]
  // Show more would find more.
  more: boolean
}

export type WebLinksOutcome = {
  created: WorkspaceDocument[]
  duplicates: { url: string; document_id: number }[]
}

const json = { "Content-Type": "application/json" }

/** `source` is `web` for the whole web, or `youtube` for its videos alone. */
export function searchWeb(
  workspaceId: number,
  query: string,
  source: string,
  page: number,
  signal?: AbortSignal
): Promise<WebResults> {
  return requestJson<WebResults>(
    `/workspaces/${workspaceId}/documents/web/search`,
    {
      method: "POST",
      headers: json,
      body: JSON.stringify({ query, source, page }),
      signal,
    }
  )
}

export async function openWebLinks(
  workspaceId: number,
  urls: string[],
  signal?: AbortSignal
): Promise<WebResult[]> {
  const opened = await requestJson<WebResults>(
    `/workspaces/${workspaceId}/documents/web/open`,
    { method: "POST", headers: json, body: JSON.stringify({ urls }), signal }
  )
  return opened.results
}

export function addWebLinks(
  workspaceId: number,
  urls: string[]
): Promise<WebLinksOutcome> {
  return requestJson<WebLinksOutcome>(
    `/workspaces/${workspaceId}/documents/web`,
    { method: "POST", headers: json, body: JSON.stringify({ urls }) }
  )
}
