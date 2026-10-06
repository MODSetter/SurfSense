import { File02Icon, Folder01Icon } from "@/components/ui/icons"

// What follows the pointer while a row is dragged. Chromium's own snapshot of
// a row inside the masked scroll area pictured the whole list.
export function DragChip({
  kind,
  name,
}: {
  kind: "folder" | "document"
  name: string
}) {
  const Icon = kind === "folder" ? Folder01Icon : File02Icon
  return (
    <div className="flex max-w-56 items-center gap-1.5 rounded-lg border bg-popover px-2 py-1 text-sm text-popover-foreground shadow-md">
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <span className="truncate">{name}</span>
    </div>
  )
}
