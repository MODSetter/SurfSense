import { intl } from "@/i18n/intl"

import { pullerName } from "./puller-names"

// Where a search runs: the whole web, or YouTube's videos alone.
export const SEARCH_SITES = ["web", "youtube"] as const

export type SearchSite = (typeof SEARCH_SITES)[number]

/** YouTube is a product name, not translated; the web is a word. */
export function searchSiteName(site: SearchSite): string {
  return site === "web"
    ? intl.formatMessage({
        id: "sources_web_site_web_label",
        defaultMessage: "Web",
      })
    : (pullerName(site) ?? site)
}
