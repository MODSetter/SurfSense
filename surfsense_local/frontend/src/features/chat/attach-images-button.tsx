import { ComposerPrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

/**
 * The composer's "+": images for this message only. Sources are added from
 * the sidebar, so a picked file is never a guess between the two.
 */
export function AttachImagesButton({
  readsImages,
  className,
}: {
  readsImages: boolean
  className?: string
}) {
  const label = intl.formatMessage({
    id: "chat_composer_attach_images_aria",
    defaultMessage: "Attach images",
  })
  const classes = cn(
    "rounded-xl aria-disabled:cursor-default aria-disabled:opacity-50",
    className
  )

  // assistant-ui's own picker, which takes the adapter's accepted types.
  const trigger = readsImages ? (
    <ComposerPrimitive.AddAttachment asChild multiple>
      <Button
        type="button"
        size="icon-lg"
        variant="ghost"
        className={classes}
        aria-label={label}
      >
        <PlusIcon className="size-5" />
      </Button>
    </ComposerPrimitive.AddAttachment>
  ) : (
    // Kept in reach, not hidden: hovering or focusing it says why it is off.
    <Button
      type="button"
      size="icon-lg"
      variant="ghost"
      className={classes}
      aria-label={label}
      disabled
      focusableWhenDisabled
    >
      <PlusIcon className="size-5" />
    </Button>
  )

  return (
    <Tooltip>
      <TooltipTrigger render={trigger} />
      <TooltipContent side="top">
        {readsImages
          ? intl.formatMessage({
              id: "chat_composer_attach_images_tooltip",
              defaultMessage: "Attach images",
            })
          : intl.formatMessage({
              id: "chat_composer_attach_images_unavailable_tooltip",
              defaultMessage: "This model can’t read images",
            })}
      </TooltipContent>
    </Tooltip>
  )
}
