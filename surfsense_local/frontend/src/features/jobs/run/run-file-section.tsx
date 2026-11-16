import { useId, useRef } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon, Upload01Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import type { WorkspaceDocument } from "@/features/sources/api"

import { chosenFiles } from "./chosen-files"
import { RunFilePicker } from "./run-file-picker"

/** The words for the kind of file a run takes, from its form's own messages. */
export type RunFileText = {
  label: string
  body: string
  // Beside the label once a file is there; the empty state has its own.
  addAnother: string
  fileAria: string
  empty: string
  add: string
  reading: (count: number) => string
}

/** The one file a run works on a copy of: picked among the ready files of
 *  its kind, or added here. */
export function RunFileSection({
  files,
  value,
  onChange,
  reading,
  accept,
  busy,
  onUpload,
  text,
}: {
  files: readonly WorkspaceDocument[]
  value: number | null
  onChange: (documentId: number) => void
  // Files of the kind still being read.
  reading: number
  accept: string
  busy: boolean
  onUpload: (files: File[]) => unknown
  text: RunFileText
}) {
  const labelId = useId()
  const input = useRef<HTMLInputElement>(null)
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
        {files.length > 0 ? (
          <Button
            type="button"
            variant="ghost"
            size="xs"
            className="shrink-0 text-muted-foreground"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            <PlusIcon data-icon="inline-start" />
            {text.addAnother}
          </Button>
        ) : null}
      </div>
      <Input
        ref={input}
        type="file"
        accept={accept}
        className="sr-only"
        aria-label={text.fileAria}
        disabled={busy}
        onChange={(event) => {
          const [file] = chosenFiles(event)
          if (file) onUpload([file])
        }}
      />
      {files.length > 0 ? (
        <RunFilePicker
          labelledBy={labelId}
          files={files}
          value={value}
          onChange={onChange}
          disabled={busy}
        />
      ) : (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-pretty text-muted-foreground">
            {text.empty}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            <Upload01Icon data-icon="inline-start" />
            {text.add}
          </Button>
        </div>
      )}
      {reading > 0 ? (
        <p role="status" className="text-sm text-muted-foreground">
          {text.reading(reading)}
        </p>
      ) : null}
    </section>
  )
}
