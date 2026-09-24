import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Trash2Icon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { YourModelRow } from "./your-model-row"

export function ModelRow({
  row,
  disabled,
  onUse,
  onDelete,
}: {
  row: YourModelRow
  disabled: boolean
  onUse: () => void
  onDelete: () => void
}) {
  return (
    <li className="flex items-center justify-between gap-3 px-3 py-2.5">
      <div className="flex min-w-0 flex-col gap-0.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium">{row.name}</span>
          {row.badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="shrink-0">
              {badge}
            </Badge>
          ))}
        </div>
        {row.note ? (
          <p className="text-xs text-muted-foreground">{row.note}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {row.selected ? (
          <Button type="button" size="sm" variant="outline" disabled>
            {intl.formatMessage({ id: "models_model_row_in_use_button" })}
          </Button>
        ) : row.target ? (
          <Button
            type="button"
            size="sm"
            disabled={disabled}
            aria-label={intl.formatMessage(
              { id: "models_model_row_use_aria" },
              { model: row.name }
            )}
            onClick={onUse}
          >
            {intl.formatMessage({ id: "models_model_row_use_button" })}
          </Button>
        ) : null}
        {row.removeId ? (
          <Button
            type="button"
            size="icon-sm"
            variant="destructive"
            disabled={disabled}
            aria-label={intl.formatMessage(
              { id: "models_model_row_delete_aria" },
              {
                model: row.name,
              }
            )}
            onClick={onDelete}
          >
            <Trash2Icon />
          </Button>
        ) : null}
      </div>
    </li>
  )
}
