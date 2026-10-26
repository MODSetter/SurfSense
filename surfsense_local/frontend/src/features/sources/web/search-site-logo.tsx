import { PluginIcon } from "@/features/plugins/plugin-icon"

import { searchSiteName, type SearchSite } from "./search-sites"

// Sites are named by their puller, logos by their plugin; Google's search is
// the one site whose puller is not a plugin of the same name.
const SITE_PLUGIN = {
  web: "google-search",
  youtube: "youtube",
  tiktok: "tiktok",
  google_maps: "google-maps",
  amazon: "amazon",
  walmart: "walmart",
  indeed: "indeed",
  reddit: "reddit",
  instagram: "instagram",
} as const satisfies Record<SearchSite, string>

/** The site's own logo, served with SurfSense's plugins. */
export function SearchSiteLogo({ site }: { site: SearchSite }) {
  return (
    <PluginIcon
      id={SITE_PLUGIN[site]}
      name={searchSiteName(site)}
      hasIcon
      firstParty
      // Bare inside a pill or a menu row: no tile, no outline.
      className="size-4 rounded-none bg-transparent p-0 text-[10px] outline-transparent dark:bg-transparent dark:outline-transparent"
    />
  )
}
