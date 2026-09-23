import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import type { Fit, Badge as FitCopy } from "./api"

/**
 * A warning, shown only when there is something to warn about, and the API owns
 * every word of it. A build that runs fully says nothing, and neither does one
 * the server may recommend, so the star and a warning never share a row.
 */
const variantFor: Record<
  Exclude<FitCopy["level"], "none">,
  "outline" | "destructive"
> = {
  // Not destructive. Reduced speed installs exactly like full speed, it just
  // runs slower, and styling it as a failure would discourage a setup that
  // measurably works.
  notice: "outline",
  refuse: "destructive",
}

export function FitBadge({
  fit,
  copy,
  className,
}: {
  fit: Fit
  copy: FitCopy
  className?: string
}) {
  if (copy.level === "none") return null
  return (
    <Badge
      variant={variantFor[copy.level]}
      className={cn("shrink-0", className)}
    >
      {fit.approximate ? `~ ${copy.verdict}` : copy.verdict}
    </Badge>
  )
}

/**
 * The explanation, dimmed and trailing, when there is one. A light spill is
 * explained here without a badge: described, not flagged.
 */
export function FitReason({ copy }: { copy: FitCopy }) {
  if (!copy.reason) return null
  return <p className="text-xs text-muted-foreground">{copy.reason}</p>
}
