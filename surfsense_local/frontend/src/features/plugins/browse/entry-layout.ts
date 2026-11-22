import { cn } from "@/lib/utils"

/** Browse shows listed plugins as cards; search lists them as rows, under the connected table. */
export type EntryLayout = "card" | "row"

export function entryClassName(layout: EntryLayout) {
  return cn(
    "relative flex gap-3 rounded-lg transition-colors",
    layout === "card"
      ? "items-start bg-muted/50 p-3 hover:bg-muted/80"
      : "items-center px-2 py-2 hover:bg-muted/50"
  )
}

/** A row matches the connected table's icon size. */
export const ROW_ICON_CLASS = "size-7 text-xs"
