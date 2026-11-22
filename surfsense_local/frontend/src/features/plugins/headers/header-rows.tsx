import { Button } from "@/components/ui/button"
import { PlusIcon, XIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

import type { SignInHeader } from "../api"

// The API takes at most this many; the screen stops offering more there.
const MOST_HEADERS = 10

/** Headers a plugin's server reads, a name and a hidden value per row. */
export function HeaderRows({
  rows,
  onChange,
  disabled = false,
}: {
  rows: SignInHeader[]
  onChange: (rows: SignInHeader[]) => void
  disabled?: boolean
}) {
  const change = (index: number, part: Partial<SignInHeader>) =>
    onChange(rows.map((row, at) => (at === index ? { ...row, ...part } : row)))
  return (
    <div className="flex flex-col gap-2">
      {rows.map((row, index) => (
        // Rows have no identity beyond their place; a removed row shifts the rest.
        <div key={index} className="flex items-center gap-2">
          <Input
            aria-label={intl.formatMessage({
              id: "plugins_headers_name_label",
              defaultMessage: "Header name",
            })}
            value={row.name}
            onChange={(event) => change(index, { name: event.target.value })}
            placeholder="x-api-key"
            autoComplete="off"
            spellCheck={false}
            className="w-2/5"
            disabled={disabled}
          />
          <Input
            aria-label={intl.formatMessage({
              id: "plugins_headers_value_label",
              defaultMessage: "Header value",
            })}
            type="password"
            autoComplete="off"
            value={row.value}
            placeholder={
              row.name.trim().toLowerCase() === "authorization"
                ? intl.formatMessage({
                    id: "plugins_headers_bearer_placeholder",
                    defaultMessage: "Bearer your-key",
                  })
                : undefined
            }
            onChange={(event) => change(index, { value: event.target.value })}
            className="flex-1"
            disabled={disabled}
          />
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={intl.formatMessage({
              id: "plugins_headers_remove_aria",
              defaultMessage: "Remove this header",
            })}
            disabled={disabled || rows.length === 1}
            onClick={() => onChange(rows.filter((_, at) => at !== index))}
          >
            <XIcon />
          </Button>
        </div>
      ))}
      {rows.length < MOST_HEADERS ? (
        <Button
          type="button"
          size="xs"
          variant="ghost"
          className="self-start"
          disabled={disabled}
          onClick={() => onChange([...rows, { name: "", value: "" }])}
        >
          <PlusIcon data-icon="inline-start" />
          {intl.formatMessage({
            id: "plugins_headers_add_button",
            defaultMessage: "Add header",
          })}
        </Button>
      ) : null}
    </div>
  )
}
