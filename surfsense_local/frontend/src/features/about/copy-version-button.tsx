import { Button } from "@/components/ui/button"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"

import { useCopyToClipboard } from "./use-copy-to-clipboard"

export function CopyVersionButton({ version }: { version: string }) {
  const { copied, copy } = useCopyToClipboard(version)
  const label = copied
    ? intl.formatMessage({
        id: "about_identity_version_copied_aria",
        defaultMessage: "Version copied",
      })
    : intl.formatMessage({
        id: "about_identity_version_copy_aria",
        defaultMessage: "Copy version",
      })

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label={label}
            className="text-muted-foreground hover:text-foreground"
            onClick={() => void copy()}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </Button>
        }
      />
      <TooltipContent side="top">{label}</TooltipContent>
    </Tooltip>
  )
}
