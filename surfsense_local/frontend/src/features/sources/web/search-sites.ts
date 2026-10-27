import { pullerName } from "./puller-names"

// Where a search can run: Google, or a site's own search through its plugin.
export const SEARCH_SITES = [
  "web",
  "youtube",
  "tiktok",
  "google_maps",
  "amazon",
  "walmart",
  "indeed",
  "reddit",
  "instagram",
] as const

export type SearchSite = (typeof SEARCH_SITES)[number]

/** Product names, not translated, as the pullers' are. */
export function searchSiteName(site: SearchSite): string {
  return site === "web" ? "Google Search" : (pullerName(site) ?? site)
}
