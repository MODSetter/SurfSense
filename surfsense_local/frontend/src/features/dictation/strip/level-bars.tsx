import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

import type { Dictation } from "../dictation-adapter"

const BARS = 9
// RMS from the room's hush to loud speech; Handy's 0.7 power keeps soft speech visible.
const QUIET_DB = -60
const LOUD_DB = -20
const CURVE = 0.7

function barHeight(level: number): number {
  const db = 20 * Math.log10(Math.max(level, 1e-6))
  const share = Math.min(1, Math.max(0, (db - QUIET_DB) / (LOUD_DB - QUIET_DB)))
  return 3 + 13 * share ** CURVE
}

/**
 * The last 9 frames' levels, newest on the right. Hidden under reduced motion,
 * where the running timer beside it says it records.
 */
export function LevelBars({ dictation }: { dictation: Dictation }) {
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
        "flex h-4 shrink-0 items-center gap-0.5 text-foreground/70 motion-reduce:hidden"
      )}
    >
      {levels.map(barHeight).map((height, index) => (
        <span
          key={index}
          className="w-0.5 rounded-full bg-current transition-[height] duration-75"
          style={{ height }}
        />
      ))}
    </span>
  )
}
