import { DotIcon } from "@/components/ui/icons"

import type { InUse } from "./your-model-row"

/**
 * Said once, above the groups: the model in use may sit inside a server group
 * that is closed, so its row alone cannot be relied on to say it.
 */
export function InUseSummary({
  slot,
  inUse,
}: {
  slot: string
  inUse: InUse | null
}) {
  return (
    <section
      aria-label={`${slot} model in use`}
      className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-muted/50 px-3 py-2.5 text-sm"
    >
      <span className="shrink-0 text-muted-foreground">In use:</span>
      {inUse ? (
        <>
          <span className="min-w-0 truncate font-medium">{inUse.name}</span>
          <DotIcon
            aria-hidden="true"
            className="size-3 shrink-0 text-muted-foreground"
          />
          <span className="shrink-0 text-muted-foreground">{inUse.source}</span>
        </>
      ) : (
        <span className="text-muted-foreground">No {slot} model chosen</span>
      )}
    </section>
  )
}
