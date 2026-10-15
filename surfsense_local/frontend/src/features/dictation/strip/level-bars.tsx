import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

import type { Dictation } from "../dictation-adapter"

const BARS = 9
// RMS from the room's hush to loud speech; Handy's 0.7 power keeps soft speech visible.
const QUIET_DB = -60
const LOUD_DB = -20
const CURVE = 0.7
const ARMING_HEIGHTS = [4, 6, 8, 10, 12, 10, 8, 6, 4]

function barHeight(level: number): number {
  const db = 20 * Math.log10(Math.max(level, 1e-6))
  const share = Math.min(1, Math.max(0, (db - QUIET_DB) / (LOUD_DB - QUIET_DB)))
  return 3 + 13 * share ** CURVE
}

/**
 * The last 9 frames' levels, newest on the right. Muted and pulsing while the
 * device starts; hidden under reduced motion, where the dot beside it stays still.
 */
export function LevelBars({
  dictation,
  arming,
}: {
  dictation: Dictation
  arming: boolean
}) {
  const [levels, setLevels] = useState<number[]>(() =>
    new Array<number>(BARS).fill(0)
  )

  useEffect(
    () =>
      dictation.subscribeLevel(() =>
        setLevels((previous) => [...previous.slice(1), dictation.getLevel()])
      ),
    [dictation]
  )

  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex h-4 shrink-0 items-center gap-0.5 motion-reduce:hidden",
        arming ? "animate-pulse text-muted-foreground/60" : "text-foreground/70"
      )}
    >
      {(arming ? ARMING_HEIGHTS : levels.map(barHeight)).map(
        (height, index) => (
          <span
            key={index}
            className="w-0.5 rounded-full bg-current transition-[height] duration-75"
            style={{ height }}
          />
        )
      )}
    </span>
  )
}
