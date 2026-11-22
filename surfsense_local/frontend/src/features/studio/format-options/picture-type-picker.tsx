import type { ComponentType } from "react"

import { ImageTypeIcon, InfographicTypeIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { StudioFormat } from "../api"
import { formatLabel } from "../studio-formats"
import { PictureCard } from "./picture-card"

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
        {types.map((entry) => (
          <PictureCard
            key={entry.key}
            name="studio-picture-type"
            value={entry.key}
            label={formatLabel(entry)}
            Art={TYPE_ART[entry.key]}
            checked={value === entry.key}
            disabled={!entry.available}
            onChange={() => onChange(entry.key)}
          />
        ))}
      </div>
    </div>
  )
}
