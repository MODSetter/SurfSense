import { SegmentedControl } from "@/components/ui/segmented-control"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { StudioFormat } from "../api"
import { formatLabel } from "../studio-formats"

/** Image or infographic, as one choice. Both need the same models, so a type is
 *  closed only if the server ever says so. */
export function PictureTypePicker({
  types,
  value,
  onChange,
}: {
  types: StudioFormat[]
  value: string
  onChange: (key: string) => void
}) {
  const label = intl.formatMessage({
    id: "studio_picture_type_label",
    defaultMessage: "Type",
  })
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <SegmentedControl
        count={types.length}
        selectedIndex={Math.max(
          0,
          types.findIndex((entry) => entry.key === value)
        )}
        role="radiogroup"
        aria-label={label}
        className="flex w-full"
      >
        {types.map((entry) => (
          <label
            key={entry.key}
            className={cn(
              "relative min-w-0 flex-1",
              entry.available
                ? "cursor-pointer"
                : "cursor-not-allowed opacity-50"
            )}
          >
            <input
              type="radio"
              name="studio-picture-type"
              value={entry.key}
              checked={value === entry.key}
              disabled={!entry.available}
              className="peer sr-only"
              onChange={() => onChange(entry.key)}
            />
            <span className="relative flex h-8 items-center justify-center truncate rounded-md px-3 text-sm peer-focus-visible:z-10 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:outline-none">
              {formatLabel(entry)}
            </span>
          </label>
        ))}
      </SegmentedControl>
    </div>
  )
}
