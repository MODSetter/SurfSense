import { useId } from "react"

import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

/** The one workbook a run fills in a copy of, a choice only among several. */
export function WorkbookPicker({
  labelledBy,
  workbooks,
  value,
  onChange,
  disabled,
}: {
  labelledBy: string
  workbooks: readonly WorkspaceDocument[]
  value: number | null
  onChange: (documentId: number) => void
  disabled?: boolean
}) {
  const baseId = useId()
  const [only] = workbooks
  if (workbooks.length === 1 && only) {
    // A lone radio reads as a choice the user could clear; one workbook is no choice.
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
      {workbooks.map((workbook) => {
        const id = `${baseId}-${workbook.id}`
        const on = workbook.id === value
        return (
          <label
            key={workbook.id}
            htmlFor={id}
            className={cn(
              "flex w-full cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm",
              on ? "border-primary bg-primary/5" : "hover:bg-accent"
            )}
          >
            <RadioGroupItem id={id} value={String(workbook.id)} />
            <OverflowTooltip
              label={workbook.title}
              focusOwner="label"
              render={
                <span className="min-w-0 flex-1 truncate">
                  {workbook.title}
                </span>
              }
            />
          </label>
        )
      })}
    </RadioGroup>
  )
}
