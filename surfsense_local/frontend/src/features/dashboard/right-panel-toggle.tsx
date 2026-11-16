import { Button } from "@/components/ui/button"
import { LayoutAlignRightIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/** Hides or shows the right panel: in the desktop's title bar, or on a heading's line in Docker. */
export function RightPanelToggle({
  open,
  controls,
  onToggle,
  className,
}: {
  open: boolean
  controls: string
  onToggle: () => void
  className?: string
}) {
  const label = open
    ? intl.formatMessage({
        id: "dashboard_right_panel_hide_aria",
        defaultMessage: "Hide right panel",
      })
    : intl.formatMessage({
        id: "dashboard_right_panel_show_aria",
        defaultMessage: "Show right panel",
      })
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className={cn("shrink-0 aria-expanded:bg-transparent", className)}
            aria-expanded={open}
            aria-controls={controls}
            aria-label={label}
            onClick={onToggle}
          >
            <LayoutAlignRightIcon />
          </Button>
        }
      />
      <TooltipContent side="bottom" collisionPadding={8}>
        {open
          ? intl.formatMessage({
              id: "dashboard_right_panel_hide_tooltip",
              defaultMessage: "Hide right panel",
            })
          : intl.formatMessage({
              id: "dashboard_right_panel_show_tooltip",
              defaultMessage: "Show right panel",
            })}
      </TooltipContent>
    </Tooltip>
  )
}
