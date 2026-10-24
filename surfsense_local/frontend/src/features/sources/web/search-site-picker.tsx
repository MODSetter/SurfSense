import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { SearchSiteLogo } from "./search-site-logo"
import { SEARCH_SITES, searchSiteName, type SearchSite } from "./search-sites"

/** The search box's pill for where a search runs. */
export function SearchSitePicker({
  site,
  onSiteChange,
}: {
  site: SearchSite
  onSiteChange: (site: SearchSite) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="outline"
            type="button"
            className="rounded-full font-normal"
            aria-label={intl.formatMessage(
              {
                id: "sources_web_site_trigger_aria",
                defaultMessage: "Search on {site}. Change site.",
              },
              { site: searchSiteName(site) }
            )}
          >
            <SearchSiteLogo site={site} />
            <span className="whitespace-nowrap">{searchSiteName(site)}</span>
            <ChevronDownIcon className="size-3.5 text-muted-foreground" />
          </Button>
        }
      />
      <DropdownMenuContent align="start" className="w-52 select-none">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {intl.formatMessage({
              id: "sources_web_site_menu_label",
              defaultMessage: "Search on",
            })}
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={site}
            onValueChange={(next) => onSiteChange(next as SearchSite)}
          >
            {SEARCH_SITES.map((choice) => (
              <DropdownMenuRadioItem key={choice} value={choice} closeOnClick>
                <SearchSiteLogo site={choice} />
                {searchSiteName(choice)}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
