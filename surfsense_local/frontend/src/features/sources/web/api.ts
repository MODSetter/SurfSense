import { requestJson } from "@/lib/api"

import type { WorkspaceDocument } from "../api"

// One to add, a list to open into its items, or a short link that can't be added.
export type LinkFit = "one" | "list" | "short_link"

export type WebResult = {
  url: string
  title: string
  description: string | null
  site: string
  // Which plugin would add it, such as "youtube"; "web_page" for any page.
  puller: string
  fit: LinkFit
}

export type WebGroup = {
  // The list link these rows came from; null for single links or a search.
  link: string | null
  results: WebResult[]
  // The list has items past these.
  more: boolean
  failed: boolean
}

export type WebLinksOutcome = {
  created: WorkspaceDocument[]
  duplicates: { url: string; document_id: number }[]
  rejected: { url: string; reason: Exclude<LinkFit, "one"> }[]
}

const json = { "Content-Type": "application/json" }

/** `source` is `web` for Google, or a site with its own search, such as `youtube`. */
export function searchWeb(
  workspaceId: number,
  query: string,
  source: string,
  page: number,
  signal?: AbortSignal
): Promise<WebGroup> {
  return requestJson<WebGroup>(
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
): Promise<WebGroup[]> {
  const opened = await requestJson<{ groups: WebGroup[] }>(
    `/workspaces/${workspaceId}/documents/web/open`,
    { method: "POST", headers: json, body: JSON.stringify({ urls }), signal }
  )
  return opened.groups
}

export function listWebLink(
  workspaceId: number,
  url: string,
  page: number
): Promise<WebGroup> {
  return requestJson<WebGroup>(
    `/workspaces/${workspaceId}/documents/web/list`,
    {
      method: "POST",
      headers: json,
      body: JSON.stringify({ url, page }),
    }
  )
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
