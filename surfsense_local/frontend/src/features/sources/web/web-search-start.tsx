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

/** Before the first search: what the box can do, and where it searches, one click away. */
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
              "Search the web or YouTube, or paste links to pages and videos. A video comes with its transcript.",
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
