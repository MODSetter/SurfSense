import { GlobalSearchIcon } from "@/components/ui/icons"
import { PluginIcon } from "@/features/plugins/plugin-icon"

import { searchSiteName, type SearchSite } from "./search-sites"

/** A globe for the web; YouTube's own logo, served with SurfSense's plugins. */
export function SearchSiteLogo({ site }: { site: SearchSite }) {
  if (site === "web") {
    return (
      <GlobalSearchIcon
        aria-hidden="true"
        className="size-4 text-muted-foreground"
      />
    )
  }
  return (
    <PluginIcon
      id={site}
      name={searchSiteName(site)}
      hasIcon
      firstParty
      // Bare inside a pill or a menu row: no tile, no outline.
      className="size-4 rounded-none bg-transparent p-0 text-[10px] outline-transparent dark:bg-transparent dark:outline-transparent"
    />
  )
}
