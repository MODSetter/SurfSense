import { Checkbox } from "@/components/ui/checkbox"
import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
import { cn } from "@/lib/utils"

import type { WorkspaceDocument } from "./api"

/** Ready sources to tick for one task, each named in full when its row cuts it off. */
export function SourceChecklist({
  documents,
  isChecked,
  onToggle,
  disabled,
}: {
  documents: readonly WorkspaceDocument[]
  isChecked: (documentId: number) => boolean
  onToggle: (documentId: number, checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <div className="space-y-1">
      {documents.map((document) => {
        const on = isChecked(document.id)
        return (
          <label
            key={document.id}
            className={cn(
              "flex w-full cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm",
              on ? "border-primary bg-primary/5" : "hover:bg-accent"
            )}
          >
            <Checkbox
              checked={on}
              disabled={disabled}
              onCheckedChange={() => onToggle(document.id, !on)}
            />
            <OverflowTooltip
              label={document.title}
              focusOwner="label"
              render={
                <span className="min-w-0 flex-1 truncate">
                  {document.title}
                </span>
              }
            />
          </label>
        )
      })}
    </div>
  )
}
