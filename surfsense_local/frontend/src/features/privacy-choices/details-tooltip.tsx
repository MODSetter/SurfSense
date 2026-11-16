import { Button } from "@/components/ui/button"
import { InformationCircleIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

/** The info icon beside a choice's title, holding its full description. */
export function DetailsTooltip({
  label,
  details,
}: {
  label: string
  details: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="bare"
            aria-label={label}
            className="inline-flex rounded-full text-muted-foreground hover:text-foreground"
          />
        }
      >
        <InformationCircleIcon className="size-3.5" />
      </TooltipTrigger>
      <TooltipContent className="max-w-80 font-normal">
        {details}
      </TooltipContent>
    </Tooltip>
  )
}
