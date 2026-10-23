import { intl } from "@/i18n/intl"

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
] as const

export type SearchSite = (typeof SEARCH_SITES)[number]

export function searchSiteName(site: SearchSite): string {
  return site === "web"
    ? intl.formatMessage({
        id: "sources_web_site_web_label",
        defaultMessage: "The web",
      })
    : (pullerName(site) ?? site)
}
