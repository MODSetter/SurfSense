import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

import {
  MentionItem,
  MentionItemDescription,
  MentionList,
} from "./mention-list"

// A name and a count per row, as the first thing `@` shows has.
const ROWS = [
  ["w-16", "w-6"],
  ["w-20", "w-6"],
] as const

/** Rows that stand where the real ones will, while the sources load. */
export function MentionRowsSkeleton() {
  return (
    <>
      {ROWS.map(([name, detail]) => (
        <MentionItem key={name} aria-hidden="true">
          <Skeleton className="size-4 shrink-0" />
          {/* One line of the row's own text tall, whatever its size. */}
          <span className="flex h-lh items-center">
            <Skeleton className={cn("h-[0.7lh]", name)} />
          </span>
          <MentionItemDescription className="flex h-lh items-center">
            <Skeleton className={cn("h-[0.7lh]", detail)} />
          </MentionItemDescription>
        </MentionItem>
      ))}
    </>
  )
}

/** The whole `@` list, for the startup frame: it has no popover yet. */
export function MentionListSkeleton() {
  return (
    // Busy, with nothing to pick yet: a group, not a listbox of no options.
    <MentionList role="group" aria-busy="true">
      <MentionRowsSkeleton />
    </MentionList>
  )
}
