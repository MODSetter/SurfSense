import { utcDay } from "../utc-calendar.ts"

const HOUR_MS = 3_600_000

export type DailyUpdateCheck = {
  /** Runs the automatic check unless one already ran this UTC day; true when it ran. */
  runIfDue(): boolean
  stop(): void
}

/**
 * Automatic checks at most once per UTC day: at launch, and from an hourly tick
 * once the day turns while the app stays open. So a day's automatic checks
 * count the installs that were open that day, with no ID on the wire.
 */
export function scheduleDailyUpdateCheck(deps: {
  /** On, and not locked off by policy. */
  automatic: () => boolean
  lastAutomaticDay: () => string | undefined
  markAutomaticDay: (day: string) => void
  check: () => void
  now?: () => Date
  every?: (run: () => void, ms: number) => () => void
}): DailyUpdateCheck {
  const now = deps.now ?? (() => new Date())
  const every =
    deps.every ??
    ((run, ms) => {
      const timer = setInterval(run, ms)
      return () => clearInterval(timer)
    })

  const runIfDue = (): boolean => {
    if (!deps.automatic()) return false
    const day = utcDay(now())
    if (deps.lastAutomaticDay() === day) return false
    // Marked before the check: a failed one waits for the next day, not the next hour.
    deps.markAutomaticDay(day)
    deps.check()
    return true
  }

  runIfDue()
  const stop = every(runIfDue, HOUR_MS)
  return { runIfDue, stop }
}
