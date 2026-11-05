import { GlobalSearchIcon, YoutubeIcon } from "@/components/ui/icons"

import type { SearchSite } from "./search-sites"

/** A globe for the web, YouTube's mark for its videos: both built in, served by nothing. */
export function SearchSiteLogo({ site }: { site: SearchSite }) {
  const Logo = site === "web" ? GlobalSearchIcon : YoutubeIcon
  return <Logo aria-hidden="true" className="size-4 text-muted-foreground" />
}
