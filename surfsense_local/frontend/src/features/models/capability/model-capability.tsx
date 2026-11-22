import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { ChevronDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { useSelection } from "../selection/use-selection"
import { chatLine, studioLine, testedLine } from "./capability-lines"

/**
 * What the chat model in use does in SurfSense, under the model in use: closed
 * until asked, so a rating never reads as a verdict beside the model's name.
 */
export function ModelCapabilitySummary() {
  const selection = useSelection("text_gen")
  const capability = selection.data?.capability
  const [open, setOpen] = useState(false)
  const regionId = useId()
  if (!capability) return null

  const title = intl.formatMessage({
    id: "models_capability_toggle_button",
    defaultMessage: "What this model can do",
  })
  const rows = [
    {
      label: intl.formatMessage({
        id: "models_capability_chat_label",
        defaultMessage: "Chat",
      }),
      line: chatLine(capability),
    },
    {
      label: intl.formatMessage({
        id: "models_capability_studio_label",
        defaultMessage: "Studio",
      }),
      line: studioLine(capability),
    },
  ]

  return (
    // Close under the In use row, inside the settings list's wider gap.
    <div className="-mt-3 flex flex-col gap-2 text-sm">
      <Button
        type="button"
        variant="bare"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((value) => !value)}
        className="-ml-1 flex w-fit items-center gap-1.5 rounded-md px-1 py-0.5 text-muted-foreground hover:text-foreground focus-visible:ring-2"
      >
        <ChevronDownIcon
          className={cn(
            "size-4 transition-transform duration-150 motion-reduce:transition-none",
            !open && "-rotate-90"
          )}
        />
        {title}
      </Button>
      {open ? (
        <section
          id={regionId}
          aria-label={title}
          className="flex flex-col gap-3 pl-6"
        >
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
            {rows.map((row) => (
              <div key={row.label} className="contents">
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd>{row.line}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-muted-foreground">
            {testedLine(capability)}
          </p>
        </section>
      ) : null}
    </div>
  )
}
