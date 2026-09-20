import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import type { Fit, Badge as FitCopy } from "./api"

/**
 * Three states, and the API owns every word of them. Copy branches on whether
 * the machine has a discrete card or unified memory, which is a fact about the
 * budget rather than about the runtime, so it is decided server side and
 * rendered verbatim here.
 *
 * "Full speed" is relative to the model, not a promise of speed in the
 * abstract: a 32B running entirely on a 4090 is still slower than a 4B.
 */
const variantFor: Record<
  Fit["state"],
  "secondary" | "outline" | "destructive"
> = {
  fits: "secondary",
  // Not destructive. Reduced speed installs exactly like full speed, it just
  // runs slower, and styling it as a failure would discourage a configuration
  // that measurably works.
  partial: "outline",
  too_big: "destructive",
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
  return (
    <Badge
      variant={variantFor[fit.state]}
      className={cn("shrink-0", className)}
    >
      {fit.approximate ? `~ ${copy.verdict}` : copy.verdict}
    </Badge>
  )
}

/**
 * The explanation, dimmed and trailing. Kept separate from the verdict because
 * the verdict is what someone choosing a model needs and the mechanism is not.
 */
export function FitReason({ copy }: { copy: FitCopy }) {
  return <p className="text-xs text-muted-foreground">{copy.reason}</p>
}
