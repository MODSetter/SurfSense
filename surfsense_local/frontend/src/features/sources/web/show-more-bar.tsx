import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/**
 * Pinned to the bottom of the results while its rows are in view: a long list
 * would otherwise hide it below its last item. `tinted` sits on a list panel.
 */
export function ShowMoreBar({
  loading,
  tinted,
  onClick,
}: {
  loading: boolean
  tinted: boolean
  onClick: () => void
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 border-t bg-popover",
        tinted && "rounded-b-lg"
      )}
    >
      <div className={cn("p-1", tinted && "rounded-b-lg bg-muted/40")}>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={loading}
          onClick={onClick}
        >
          {loading ? <Spinner /> : null}
          {intl.formatMessage({
            id: "sources_web_show_more_button",
            defaultMessage: "Show more",
          })}
        </Button>
      </div>
    </div>
  )
}
