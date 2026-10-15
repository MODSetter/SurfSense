import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Folder01Icon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import {
  TOP,
  subtreeOf,
  type FolderKey,
  type SourceIndex,
} from "./source-index"

/** A folder or a source to move, and where it sits now. */
export type MoveTarget = {
  kind: "folder" | "document"
  id: number
  name: string
  from: FolderKey
}

type Destination = { key: FolderKey; name: string; level: number }

function destinationsFor(index: SourceIndex, target: MoveTarget) {
  // A folder can't go inside itself.
  const barred =
    target.kind === "folder" ? subtreeOf(index, target.id) : new Set<number>()
  const destinations: Destination[] = [
    {
      key: TOP,
      name: intl.formatMessage({
        id: "sources_move_library_label",
        defaultMessage: "Library",
      }),
      level: 0,
    },
  ]
  const walk = (key: FolderKey, level: number) => {
    for (const id of index.childFolders.get(key) ?? []) {
      if (barred.has(id)) continue
      destinations.push({
        key: id,
        name: index.folders.get(id)?.name ?? "",
        level,
      })
      walk(id, level + 1)
    }
  }
  walk(TOP, 1)
  return destinations
}

/** The keyboard's way to move a row: pick a folder, then Move. */
export function MoveToDialog({
  index,
  target,
  open,
  onOpenChange,
  onOpenChangeComplete,
  onMove,
}: {
  index: SourceIndex
  target: MoveTarget | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
  onMove: (target: MoveTarget, to: FolderKey) => Promise<boolean>
}) {
  const [picked, setPicked] = useState<FolderKey | undefined>(undefined)
  const [moving, setMoving] = useState(false)
  const destinations = target ? destinationsFor(index, target) : []
  const chosen = picked === undefined ? target?.from : picked
  const canMove = target !== null && chosen !== target.from && !moving

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!target || chosen === undefined || !canMove) return
    setMoving(true)
    const moved = await onMove(target, chosen)
    setMoving(false)
    if (moved) onOpenChange(false)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(next) => {
        if (!next) setPicked(undefined)
        onOpenChangeComplete(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <form
          className="flex min-w-0 flex-col gap-4"
          onSubmit={(event) => void submit(event)}
        >
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage(
                {
                  id: "sources_move_dialog_title",
                  defaultMessage: "Move {name}",
                },
                { name: target?.name ?? "" }
              )}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage({
                id: "sources_move_dialog_body",
                defaultMessage: "Choose the folder to move it to.",
              })}
            </DialogDescription>
          </DialogHeader>
          <ScrollFade className="max-h-72 min-h-0">
            <div
              role="radiogroup"
              aria-label={intl.formatMessage({
                id: "sources_move_destinations_aria",
                defaultMessage: "Folders",
              })}
              className="flex flex-col gap-0.5"
            >
              {destinations.map((destination) => (
                <label
                  key={destination.key ?? "top"}
                  className={cn(
                    "flex h-8 cursor-pointer items-center gap-2 rounded-md pr-2 text-sm has-focus-visible:ring-2 has-focus-visible:ring-ring/50",
                    chosen === destination.key
                      ? "bg-primary/5 text-foreground"
                      : "hover:bg-muted"
                  )}
                  style={{ paddingLeft: 8 + destination.level * 16 }}
                >
                  <input
                    type="radio"
                    name="move-destination"
                    className="sr-only"
                    checked={chosen === destination.key}
                    onChange={() => setPicked(destination.key)}
                  />
                  <Folder01Icon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate">
                    {destination.name}
                  </span>
                </label>
              ))}
            </div>
          </ScrollFade>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {intl.formatMessage({
                id: "sources_move_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!canMove}>
              {intl.formatMessage({
                id: "sources_move_submit_button",
                defaultMessage: "Move",
              })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
