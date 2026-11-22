import { useId, useRef } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import {
  SOURCE_FILE_ACCEPT,
  type WorkspaceDocument,
} from "@/features/sources/api"
import { SourceChecklist } from "@/features/sources/source-checklist"
import { intl } from "@/i18n/intl"

import { chosenFiles } from "./chosen-files"

/** The words for the sources a run rests on, from its form's own messages. */
export type EvidenceText = {
  label: string
  body: string
  add: string
  fileAria: string
  chosen: (count: number) => string
  none: string
  empty: string
  reading: (count: number) => string
}

/** The ready sources a run rests on, ticked here or added. */
export function EvidenceChecklist({
  choices,
  chosen,
  onMark,
  reading,
  busy,
  onUpload,
  text,
}: {
  choices: readonly WorkspaceDocument[]
  chosen: readonly number[]
  onMark: (documentIds: readonly number[], on: boolean) => void
  // Other sources still being read, which can be chosen once ready.
  reading: number
  busy: boolean
  onUpload: (files: File[]) => unknown
  text: EvidenceText
}) {
  const labelId = useId()
  const input = useRef<HTMLInputElement>(null)
  const everyChosen = choices.length > 0 && chosen.length === choices.length
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h4 id={labelId} className="text-sm font-medium">
            {text.label}
          </h4>
          <p className="text-sm text-pretty text-muted-foreground">
            {text.body}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {choices.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              disabled={busy}
              onClick={() =>
                onMark(
                  choices.map((choice) => choice.id),
                  !everyChosen
                )
              }
            >
              {everyChosen
                ? intl.formatMessage({
                    id: "jobs_run_sources_deselect_all_button",
                    defaultMessage: "Deselect all",
                  })
                : intl.formatMessage({
                    id: "jobs_run_sources_select_all_button",
                    defaultMessage: "Select all",
                  })}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="xs"
            className="text-muted-foreground"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            <PlusIcon data-icon="inline-start" />
            {text.add}
          </Button>
        </div>
      </div>
      <Input
        ref={input}
        type="file"
        multiple
        accept={SOURCE_FILE_ACCEPT}
        className="sr-only"
        aria-label={text.fileAria}
        disabled={busy}
        onChange={(event) => {
          const files = chosenFiles(event)
          if (files.length > 0) onUpload(files)
        }}
      />
      {choices.length > 0 ? (
        <>
          <div role="group" aria-labelledby={labelId}>
            <SourceChecklist
              documents={choices}
              isChecked={(documentId) => chosen.includes(documentId)}
              onToggle={(documentId, on) => onMark([documentId], on)}
              disabled={busy}
            />
          </div>
          {chosen.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              {text.chosen(chosen.length)}
            </p>
          ) : (
            <p role="status" className="text-sm text-muted-foreground">
              {text.none}
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-pretty text-muted-foreground">
          {text.empty}
        </p>
      )}
      {reading > 0 ? (
        <p role="status" className="text-sm text-muted-foreground">
          {text.reading(reading)}
        </p>
      ) : null}
    </section>
  )
}
