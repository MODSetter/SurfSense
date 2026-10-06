import { SearchIcon, XIcon } from "@/components/ui/icons"

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { intl } from "@/i18n/intl"

// The name filter, opened in place of the header's title. Closing clears it,
// so a hidden filter never hides sources.
export function SourceFilterField({
  value,
  onChange,
  onClose,
}: {
  value: string
  onChange: (value: string) => void
  onClose: (returnFocus: boolean) => void
}) {
  return (
    <InputGroup className="h-7 min-w-0 flex-1">
      <InputGroupAddon>
        <SearchIcon />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        autoFocus
        value={value}
        placeholder={intl.formatMessage({
          id: "sources_filter_placeholder",
          defaultMessage: "Filter by name",
        })}
        aria-label={intl.formatMessage({
          id: "sources_filter_aria",
          defaultMessage: "Filter sources by name",
        })}
        // The close button below replaces the browser's own clear button.
        className="[&::-webkit-search-cancel-button]:appearance-none"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Escape") return
          // Keeps a surrounding dialog or popup from closing too.
          event.stopPropagation()
          onClose(true)
        }}
        // An empty field left behind folds back into the header.
        onBlur={() => {
          if (value === "") onClose(false)
        }}
      />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label={intl.formatMessage({
            id: "sources_filter_close_aria",
            defaultMessage: "Close filter",
          })}
          onClick={() => onClose(true)}
        >
          <XIcon />
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  )
}
