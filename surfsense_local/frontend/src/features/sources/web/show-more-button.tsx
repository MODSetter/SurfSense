import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

/** The end of a search's or a list's rows, scrolling with them. */
export function ShowMoreButton({
  loading,
  onClick,
}: {
  loading: boolean
  onClick: () => void
}) {
  const label = intl.formatMessage({
    id: "sources_web_show_more_button",
    defaultMessage: "Show more",
  })
  return (
    // Centred under the rows, in the shape of their Add.
    <div className="flex justify-center px-3 py-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={loading}
        aria-label={label}
        onClick={onClick}
        // A fixed width keeps it still while the spinner replaces the label.
        className="min-w-20"
      >
        {loading ? <Spinner /> : label}
      </Button>
    </div>
  )
}
