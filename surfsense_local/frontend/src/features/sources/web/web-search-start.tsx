import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { GlobalSearchIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { SearchSiteLogo } from "./search-site-logo"
import { SEARCH_SITES, searchSiteName, type SearchSite } from "./search-sites"

/** Before the first search: what the box can do, and every site one click away. */
export function WebSearchStart({
  site,
  onSiteChange,
}: {
  site: SearchSite
  onSiteChange: (site: SearchSite) => void
}) {
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        {/* The license offer's icon, so both states of this space read as one. */}
        <EmptyMedia variant="icon">
          <GlobalSearchIcon />
        </EmptyMedia>
        <EmptyTitle>
          {intl.formatMessage({
            id: "sources_web_start_title",
            defaultMessage: "Find sources on the web",
          })}
        </EmptyTitle>
        <EmptyDescription>
          {intl.formatMessage({
            id: "sources_web_start_body",
            defaultMessage:
              "Pick where to search, or paste links to pages, videos, posts, channels and products.",
          })}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="max-w-xl flex-row flex-wrap justify-center gap-2">
        {SEARCH_SITES.map((choice) => (
          <Button
            key={choice}
            type="button"
            variant="outline"
            className="rounded-full font-normal aria-pressed:border-ring/60 aria-pressed:bg-muted"
            aria-pressed={choice === site}
            onClick={() => onSiteChange(choice)}
          >
            <SearchSiteLogo site={choice} />
            {searchSiteName(choice)}
          </Button>
        ))}
      </EmptyContent>
    </Empty>
  )
}
