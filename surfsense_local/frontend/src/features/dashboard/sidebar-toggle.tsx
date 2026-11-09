import { Button } from "@/components/ui/button"
import { LayoutAlignLeftIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

function shortcutLabel() {
  const mac =
    window.surfsense?.platform === "darwin" ||
    /Mac/.test(window.navigator.platform)
  return mac ? "⌘B" : "Ctrl+B"
}

/** Hides or shows the left sidebar: in the desktop's title bar, or beside the logo and on the chat's heading in Docker. */
export function SidebarToggle({
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
        id: "dashboard_sidebar_hide_aria",
        defaultMessage: "Hide sidebar",
      })
    : intl.formatMessage({
        id: "dashboard_sidebar_show_aria",
        defaultMessage: "Show sidebar",
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
            <LayoutAlignLeftIcon />
          </Button>
        }
      />
      <TooltipContent side="bottom" collisionPadding={8}>
        {open
          ? intl.formatMessage(
              {
                id: "dashboard_sidebar_hide_tooltip",
                defaultMessage: "Hide sidebar ({shortcut})",
              },
              { shortcut: shortcutLabel() }
            )
          : intl.formatMessage(
              {
                id: "dashboard_sidebar_show_tooltip",
                defaultMessage: "Show sidebar ({shortcut})",
              },
              { shortcut: shortcutLabel() }
            )}
      </TooltipContent>
    </Tooltip>
  )
}
