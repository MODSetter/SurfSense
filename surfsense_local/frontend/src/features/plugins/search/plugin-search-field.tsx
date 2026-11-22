import { SearchIcon, XIcon } from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { intl } from "@/i18n/intl"

/** Searches connected and listed plugins at once; Escape or the clear button gives the tabs back. */
export function PluginSearchField({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  return (
    <InputGroup className="h-8 w-56 min-w-0 shrink">
      <InputGroupAddon>
        <SearchIcon />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        value={value}
        placeholder={intl.formatMessage({
          id: "plugins_search_placeholder",
          defaultMessage: "Search plugins",
        })}
        aria-label={intl.formatMessage({
          id: "plugins_search_aria",
          defaultMessage: "Search plugins",
        })}
        // The clear button below replaces the browser's own. text-sm holds at every width.
        className="text-sm [&::-webkit-search-cancel-button]:appearance-none"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Escape" || value === "") return
          // Keeps the settings dialog open: Escape clears the search first.
          event.stopPropagation()
          onChange("")
        }}
      />
      {value ? (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-label={intl.formatMessage({
              id: "plugins_search_clear_aria",
              defaultMessage: "Clear search",
            })}
            onClick={() => onChange("")}
          >
            <XIcon />
          </InputGroupButton>
        </InputGroupAddon>
      ) : null}
    </InputGroup>
  )
}
