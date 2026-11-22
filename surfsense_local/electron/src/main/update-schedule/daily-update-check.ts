import { utcDay } from "../utc-calendar.ts"

const HOUR_MS = 3_600_000
// A check that read no manifest (offline at launch, both hosts down) is retried
// on the hourly tick, this many tries a UTC day at most.
const MAX_TRIES_PER_DAY = 3

export type DailyUpdateCheck = {
  /** Runs the automatic check unless one already read a manifest this UTC day; true when it ran. */
  runIfDue(): Promise<boolean>
  stop(): void
}

/**
 * Automatic checks at most once per UTC day: at launch, and from an hourly tick
 * once the day turns while the app stays open. So a day's automatic checks
 * count the installs that were open that day, with no ID on the wire; only a
 * check that read no manifest is tried again.
 */
export function scheduleDailyUpdateCheck(deps: {
  /** On, and not locked off by policy. */
  automatic: () => boolean
  lastAutomaticDay: () => string | undefined
  markAutomaticDay: (day: string) => void
  /** Resolves true once a manifest was read, from either host. */
  check: () => Promise<boolean>
  now?: () => Date
  every?: (run: () => Promise<boolean>, ms: number) => () => void
}): DailyUpdateCheck {
  const now = deps.now ?? (() => new Date())
  const every =
    deps.every ??
    ((run, ms) => {
      const timer = setInterval(run, ms)
      return () => clearInterval(timer)
    })
  let running = false
  let tries = { day: "", count: 0 }

  const runIfDue = async (): Promise<boolean> => {
    if (running || !deps.automatic()) return false
    const day = utcDay(now())
    if (deps.lastAutomaticDay() === day) return false
    const count = tries.day === day ? tries.count : 0
    if (count >= MAX_TRIES_PER_DAY) return false
    tries = { day, count: count + 1 }
    running = true
    try {
      if (await deps.check().catch(() => false)) deps.markAutomaticDay(day)
    } finally {
      running = false
    }
    return true
  }

  void runIfDue()
  const stop = every(runIfDue, HOUR_MS)
  return { runIfDue, stop }
}
