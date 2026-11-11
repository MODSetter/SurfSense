import type { ComponentType } from "react"

import {
  CheckIcon,
  ImageTypeIcon,
  InfographicTypeIcon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { StudioFormat } from "../api"
import { formatLabel } from "../studio-formats"

const TYPE_ART: Record<string, ComponentType<{ className?: string }>> = {
  image: ImageTypeIcon,
  infographic: InfographicTypeIcon,
}

/** Image or infographic as cards, each shown by its picture, the chosen one ticked.
 *  Both need the same models, so a type is closed only if the server ever says so. */
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
      <div
        role="radiogroup"
        aria-label={label}
        className="grid grid-cols-2 gap-2"
      >
        {types.map((entry) => {
          const Art = TYPE_ART[entry.key]
          const checked = value === entry.key
          return (
            <label
              key={entry.key}
              className={cn(
                "group relative flex min-w-0 flex-col gap-1.5",
                entry.available
                  ? "cursor-pointer"
                  : "cursor-not-allowed opacity-50"
              )}
            >
              <input
                type="radio"
                name="studio-picture-type"
                value={entry.key}
                checked={checked}
                disabled={!entry.available}
                className="peer sr-only"
                onChange={() => onChange(entry.key)}
              />
              <span
                className={cn(
                  "relative flex aspect-3/2 items-center justify-center overflow-hidden rounded-lg border transition-colors duration-150 ease-out peer-focus-visible:ring-2 peer-focus-visible:ring-ring motion-reduce:transition-none",
                  checked
                    ? "border-primary ring-1 ring-primary"
                    : "border-border group-hover:border-foreground/30"
                )}
              >
                {Art ? <Art /> : null}
                {checked ? (
                  <span className="absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <CheckIcon className="size-3" strokeWidth={2.5} />
                  </span>
                ) : null}
              </span>
              <span className="truncate text-sm">{formatLabel(entry)}</span>
            </label>
          )
        })}
      </div>
    </div>
  )
}
