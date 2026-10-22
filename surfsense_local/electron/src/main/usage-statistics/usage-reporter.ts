import type { UsageLockReason } from "../admin-policy/policy-locks.ts"
import type { OsLabel, PlatformLabel } from "../system-labels.ts"
import { utcDay } from "../utc-calendar.ts"
import { activeFlags, reportedToday, reportPeriod } from "./active-flags.ts"
import type { PrivacyFile, PrivacyStore } from "./privacy-file.ts"
import { buildUsageReport, type UsageReport } from "./report-body.ts"

// Contract 05, part B: one accepted report per UTC day, three tries at most,
// 10 s each, and never more than 4 KB.
const MAX_ATTEMPTS_PER_DAY = 3
const SEND_TIMEOUT_MS = 10_000
const MAX_BODY_BYTES = 4096
// After launch, so a report never competes with the API starting up.
const FIRST_ATTEMPT_DELAY_MS = 2 * 60_000
const HOUR_MS = 3_600_000
const WEEK_MS = 7 * 86_400_000

export type AttemptResult = "sent" | "failed" | "skipped"

export type UsageReporter = {
  /** One try, if allowed now; the schedule calls it, tests call it directly. */
  attempt(): Promise<AttemptResult>
  /** The exact next body, built but not sent; null where this machine has no contract label. */
  preview(): Promise<UsageReport | null>
  /** First try about two minutes after launch, then an hourly tick. */
  start(): void
  /** A try about two minutes from now, after the user turns reports on. */
  nudge(): void
  stop(): void
}

type Timers = {
  after(run: () => void, ms: number): () => void
  every(run: () => void, ms: number): () => void
}

const realTimers: Timers = {
  after(run, ms) {
    const timer = setTimeout(run, ms)
    return () => clearTimeout(timer)
  },
  every(run, ms) {
    const timer = setInterval(run, ms)
    return () => clearInterval(timer)
  },
}

export function createUsageReporter(deps: {
  store: PrivacyStore
  lock: UsageLockReason | null
  /** null in a development build without SURFSENSE_TELEMETRY_DEV_ENDPOINT. */
  endpoint: string | null
  facts: { appVersion: string; platform: PlatformLabel | null; os: OsLabel | null }
  summary: (since: Date) => Promise<unknown>
  locale: () => string
  totalMemoryBytes: () => number
  fetch: typeof fetch
  now?: () => Date
  timers?: Timers
  log?: (line: string) => void
  onSent?: () => void
}): UsageReporter {
  const now = deps.now ?? (() => new Date())
  const timers = deps.timers ?? realTimers
  const log = deps.log ?? (() => undefined)
  const { platform, os, appVersion } = deps.facts
  const host = deps.endpoint ? new URL(deps.endpoint).host : null
  let inFlight = false
  let cancelNudge: (() => void) | null = null
  const stops: Array<() => void> = []

  const build = async (file: PrivacyFile, at: Date): Promise<UsageReport | null> => {
    if (platform === null || os === null) return null
    const summary = await deps.summary(new Date(at.getTime() - WEEK_MS))
    return buildUsageReport({
      appVersion,
      platform,
      os,
      firstRunAt: file.firstRunAt,
      flags: activeFlags(file.lastReport, at),
      summary,
      locale: deps.locale(),
      totalMemoryBytes: deps.totalMemoryBytes(),
    })
  }

  // Only an explicit yes sends: off, never asked, a policy, DO_NOT_TRACK or a
  // development build each keep every report on the machine.
  const allowed = (file: PrivacyFile): boolean =>
    file.usageStatistics === true &&
    deps.lock === null &&
    deps.endpoint !== null &&
    platform !== null &&
    os !== null

  const attempt = async (): Promise<AttemptResult> => {
    if (inFlight) return "skipped"
    const file = deps.store.read()
    if (!allowed(file)) return "skipped"
    const at = now()
    if (reportedToday(file.lastReport, at)) return "skipped"
    const day = utcDay(at)
    const tries = file.attempts?.day === day ? file.attempts.count : 0
    if (tries >= MAX_ATTEMPTS_PER_DAY) return "skipped"
    deps.store.update((current) => ({ ...current, attempts: { day, count: tries + 1 } }))
    inFlight = true
    try {
      const body = await build(file, at)
      if (body === null) return "skipped"
      const json = JSON.stringify(body)
      if (Buffer.byteLength(json) > MAX_BODY_BYTES) {
        log("usage report not sent: over 4 KB")
        return "failed"
      }
      // Asked again: the user may have said no while the summary was read.
      if (!allowed(deps.store.read())) {
        log("usage report not sent: switched off while it was being built")
        return "skipped"
      }
      const reply = await deps.fetch(deps.endpoint!, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json,
        credentials: "omit",
        cache: "no-store",
        // Never re-sent to wherever a redirect points.
        redirect: "error",
        signal: AbortSignal.timeout(SEND_TIMEOUT_MS),
      })
      if (!reply.ok) {
        log(`usage report to ${host} not accepted (HTTP ${reply.status}), try ${tries + 1} of 3 today`)
        return "failed"
      }
      deps.store.update((current) => ({
        ...current,
        lastReport: reportPeriod(at),
        lastSent: { at: at.toISOString(), body },
      }))
      log(`usage report sent to ${host}`)
      deps.onSent?.()
      return "sent"
    } catch (error) {
      const reason = error instanceof Error && error.name === "TimeoutError" ? "timed out" : "unreachable"
      log(`usage report to ${host} ${reason}, try ${tries + 1} of 3 today`)
      return "failed"
    } finally {
      inFlight = false
    }
  }

  const run = () => void attempt()

  return {
    attempt,
    preview: async () => {
      const at = now()
      return build(deps.store.read(), at)
    },
    start() {
      stops.push(timers.after(run, FIRST_ATTEMPT_DELAY_MS))
      stops.push(timers.every(run, HOUR_MS))
    },
    nudge() {
      cancelNudge?.()
      cancelNudge = timers.after(run, FIRST_ATTEMPT_DELAY_MS)
    },
    stop() {
      cancelNudge?.()
      for (const stop of stops.splice(0)) stop()
    },
  }
}
