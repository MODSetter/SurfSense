import { Button } from "@/components/ui/button"
import { ArrowLeftIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

/** Back from a job's view to the list; held while that view's request is out. */
export function AllJobsButton({
  onClick,
  disabled,
}: {
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="-ml-2 self-start text-muted-foreground"
      disabled={disabled}
      onClick={onClick}
    >
      <ArrowLeftIcon data-icon="inline-start" />
      {intl.formatMessage({
        id: "jobs_dialog_back_button",
        defaultMessage: "All jobs",
      })}
    </Button>
  )
}
