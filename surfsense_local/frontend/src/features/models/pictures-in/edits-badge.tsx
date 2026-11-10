import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"

/** Marks an image model that takes a picture in. Information only: any image
 *  model can be chosen, and one without it changes a picture by redrawing. */
export function EditsBadge() {
  const label = intl.formatMessage({
    id: "models_edits_badge_label",
    defaultMessage: "Edits",
  })
  const tip = intl.formatMessage({
    id: "models_edits_badge_tooltip",
    defaultMessage: "Can edit pictures",
  })
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          // Focusable, so the tooltip opens from the keyboard too; named in
          // full, since the tooltip is only seen.
          <Badge
            variant="secondary"
            tabIndex={0}
            role="note"
            aria-label={intl.formatMessage(
              {
                id: "models_edits_badge_aria",
                defaultMessage: "{label}: can edit pictures",
              },
              { label }
            )}
          />
        }
      >
        {label}
      </TooltipTrigger>
      <TooltipContent side="top">{tip}</TooltipContent>
    </Tooltip>
  )
}
