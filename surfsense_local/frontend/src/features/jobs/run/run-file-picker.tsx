import { useId } from "react"

import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

/** The one file a run makes a copy of, a choice only among several. */
export function RunFilePicker({
  labelledBy,
  files,
  value,
  onChange,
  disabled,
}: {
  labelledBy: string
  files: readonly WorkspaceDocument[]
  value: number | null
  onChange: (documentId: number) => void
  disabled?: boolean
}) {
  const baseId = useId()
  const [only] = files
  if (files.length === 1 && only) {
    // A lone radio reads as a choice the user could clear; one file is no choice.
    return (
      <div role="group" aria-labelledby={labelledBy}>
        <p className="rounded-md border border-primary bg-primary/5 px-2.5 py-2 text-sm wrap-anywhere">
          {only.title}
        </p>
      </div>
    )
  }
  return (
    <RadioGroup
      aria-labelledby={labelledBy}
      value={value === null ? "" : String(value)}
      onValueChange={(next) => onChange(Number(next))}
      disabled={disabled}
      className="gap-1"
    >
      {files.map((file) => {
        const id = `${baseId}-${file.id}`
        const on = file.id === value
        return (
          <label
            key={file.id}
            htmlFor={id}
            className={cn(
              "flex w-full cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm",
              on ? "border-primary bg-primary/5" : "hover:bg-accent"
            )}
          >
            <RadioGroupItem id={id} value={String(file.id)} />
            <OverflowTooltip
              label={file.title}
              focusOwner="label"
              render={
                <span className="min-w-0 flex-1 truncate">{file.title}</span>
              }
            />
          </label>
        )
      })}
    </RadioGroup>
  )
}
