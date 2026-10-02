import { useState } from "react"

import { BrainCircuitIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { modelControlButtonClassName } from "./model-picker"
import { readThinkingOn, writeThinkingOn } from "./thinking-preference"

/**
 * Whether the next answers think first. Read from storage when a message is
 * sent, so this only shows and changes the preference.
 */
export function ThinkingToggle({
  canSkip,
  className,
}: {
  // False for a model that cannot be told to stop: the switch stays on.
  canSkip: boolean
  className?: string
}) {
  const [stored, setStored] = useState(readThinkingOn)
  const on = stored || !canSkip
  const toggle = () => {
    if (!canSkip) return
    writeThinkingOn(!on)
    setStored(!on)
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          // Kept in reach, not hidden: hovering or focusing it says why it is held.
          <button
            type="button"
            aria-pressed={on}
            aria-disabled={!canSkip}
            className={cn(
              modelControlButtonClassName,
              on && "text-foreground",
              !canSkip && "cursor-default opacity-50 hover:bg-transparent",
              className
            )}
            onClick={toggle}
          >
            <BrainCircuitIcon className="size-3.5" />
            {intl.formatMessage({
              id: "chat_composer_thinking_label",
              defaultMessage: "Thinking",
            })}
          </button>
        }
      />
      <TooltipContent side="top">
        {!canSkip
          ? intl.formatMessage({
              id: "chat_composer_thinking_unavailable_tooltip",
              defaultMessage: "Only a local model can answer without thinking",
            })
          : on
            ? intl.formatMessage({
                id: "chat_composer_thinking_on_tooltip",
                defaultMessage:
                  "Thinks before answering. Turn off to answer sooner.",
              })
            : intl.formatMessage({
                id: "chat_composer_thinking_off_tooltip",
                defaultMessage: "Answers without thinking first",
              })}
      </TooltipContent>
    </Tooltip>
  )
}
