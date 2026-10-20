import { SegmentedControl } from "@/components/ui/segmented-control"
import { intl } from "@/i18n/intl"

import type { SendAs } from "./connection-draft"

const OPTIONS: { value: SendAs; label: () => string }[] = [
  {
    value: "bearer",
    label: () =>
      intl.formatMessage({
        id: "plugins_connection_bearer_label",
        defaultMessage: "Bearer",
      }),
  },
  {
    value: "basic",
    label: () =>
      intl.formatMessage({
        id: "plugins_connection_basic_label",
        defaultMessage: "Basic",
      }),
  },
  {
    value: "custom",
    label: () =>
      intl.formatMessage({
        id: "plugins_connection_custom_label",
        defaultMessage: "Custom header",
      }),
  },
]

/** How the key is sent, as a choice of three. */
export function SendAsControl({
  value,
  onChange,
  disabled,
}: {
  value: SendAs
  onChange: (value: SendAs) => void
  disabled: boolean
}) {
  return (
    <SegmentedControl
      count={OPTIONS.length}
      selectedIndex={OPTIONS.findIndex((option) => option.value === value)}
      role="radiogroup"
      aria-label={intl.formatMessage({
        id: "plugins_connection_send_as_aria",
        defaultMessage: "Send the key as",
      })}
      className="grid w-full grid-cols-3"
    >
      {OPTIONS.map((option) => (
        <label
          key={option.value}
          className="relative flex h-7 cursor-pointer items-center justify-center rounded-md px-2 text-xs font-medium"
        >
          <input
            type="radio"
            name="send-as"
            value={option.value}
            checked={value === option.value}
            disabled={disabled}
            className="peer sr-only"
            onChange={() => onChange(option.value)}
          />
          <span className="relative peer-focus-visible:rounded-md peer-focus-visible:ring-2 peer-focus-visible:ring-ring">
            {option.label()}
          </span>
        </label>
      ))}
    </SegmentedControl>
  )
}
