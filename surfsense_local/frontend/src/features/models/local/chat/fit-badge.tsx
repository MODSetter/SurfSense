import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import type { Fit, Badge as FitCopy } from "./api"
import { fitReason, fitVerdict } from "./fit-text"

/**
 * A warning, shown only when there is something to warn about. The API decides
 * which one, and `fit-text.ts` words it. A build that runs fully says nothing,
 * and neither does one the server may recommend, so the star and a warning
 * never share a row.
 */
const variantFor: Record<
  Exclude<FitCopy["level"], "none">,
  "warning" | "destructive"
> = {
  // Amber, not red. Reduced speed installs exactly like full speed, it just
  // runs slower, and styling it as a failure would discourage a setup that
  // measurably works.
  notice: "warning",
  refuse: "destructive",
}

export function FitBadge({
  fit,
  copy,
  className,
}: {
  fit: Fit | null
  copy: FitCopy | null
  className?: string
}) {
  // No copy is no estimate at all, which says nothing rather than "fits".
  if (!fit || !copy || copy.level === "none") return null
  const verdict = fitVerdict(copy)
  return (
    <Badge
      variant={variantFor[copy.level]}
      className={cn("shrink-0", className)}
    >
      {fit.approximate ? `~ ${verdict}` : verdict}
    </Badge>
  )
}

/**
 * The explanation, dimmed and trailing, when there is one. A light spill is
 * explained here without a badge: described, not flagged.
 */
export function FitReason({
  fit,
  copy,
}: {
  fit: Fit | null
  copy: FitCopy | null
}) {
  if (!copy?.reason) return null
  return <p className="text-xs text-muted-foreground">{fitReason(copy, fit)}</p>
}
