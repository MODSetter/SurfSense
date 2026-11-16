import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { ChevronDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { listLanguages } from "./language-names"

/** The languages a model is listed for: counted, named once opened. */
export function ListedLanguages({ codes }: { codes: readonly string[] }) {
  const listId = useId()
  const [open, setOpen] = useState(false)

  // One language is named in the row's facts instead.
  if (codes.length < 2) return null

  return (
    <div className="flex flex-col gap-1">
      <Button
        type="button"
        variant="ghost"
        size="xs"
        aria-expanded={open}
        aria-controls={listId}
        // Keeps the chevron in line with the row's text above it.
        className="-ml-1.5 self-start text-muted-foreground"
        onClick={() => setOpen((value) => !value)}
      >
        <ChevronDownIcon
          aria-hidden="true"
          data-icon="inline-start"
          className={cn(
            "size-3 transition-transform motion-reduce:transition-none",
            open && "rotate-180"
          )}
        />
        {intl.formatMessage(
          {
            id: "models_speech_model_languages_button",
            defaultMessage:
              "{count, plural, one {# language} other {# languages}}",
          },
          { count: codes.length }
        )}
      </Button>
      {open ? (
        <p id={listId} className="text-xs text-pretty text-muted-foreground">
          {listLanguages(codes)}
        </p>
      ) : null}
    </div>
  )
}
