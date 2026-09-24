import { Loader2Icon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

function Spinner({
  className,
  ...props
}: React.ComponentProps<typeof Loader2Icon>) {
  return (
    <Loader2Icon
      data-slot="spinner"
      role="status"
      aria-label={intl.formatMessage({ id: "app_spinner_aria" })}
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
