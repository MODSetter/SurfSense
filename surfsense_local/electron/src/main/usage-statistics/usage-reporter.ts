import type { UsageLockReason } from "../admin-policy/policy-locks.ts"
import type { OsLabel, PlatformLabel } from "../system-labels.ts"
import { utcDay } from "../utc-calendar.ts"
import { activeFlags, reportedToday, reportPeriod, type ActiveFlags } from "./active-flags.ts"
import {
  carriesHardware,
  carriesWeek,
  inFirstWeek,
  weekSince,
  type ReportTrigger,
} from "./first-week.ts"
import { sentHardware, type PrivacyFile, type PrivacyStore } from "./privacy-file.ts"
import { buildUsageReport, type UsageReport } from "./report-body.ts"
import { furthestStep, setupReportDue, setupStep } from "./setup-progress.ts"
import { countSetupTry, refusedSetupTry, setupTryAllowed } from "./setup-tries.ts"

// Contract 05, part B: one accepted daily report per UTC day, three tries at
// most, 10 s each, and never more than 4 KB.
const MAX_ATTEMPTS_PER_DAY = 3
const SEND_TIMEOUT_MS = 10_000
const MAX_BODY_BYTES = 4096
// After launch, so a report never competes with the API starting up.
const FIRST_ATTEMPT_DELAY_MS = 2 * 60_000
const HOUR_MS = 3_600_000
// Revision 1.1, part D: how often the first week looks for a new setup step.
const SETUP_CHECK_MS = 5 * 60_000
// A setup report counts no one as active; only the daily report does.
const NO_FLAGS: ActiveFlags = { first: false, week: false, month: false }

export type AttemptResult = "sent" | "failed" | "skipped"

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error))

export type UsageReporter = {
  /** One try at the daily report, if allowed now; the schedule calls it, tests call it directly. */
  attempt(): Promise<AttemptResult>
  /** One look for a setup step no report carried yet, sent as a setup report; first week only. */
  checkSetup(): Promise<AttemptResult>
  /** The exact next daily body, built but not sent; null where this machine has no contract label. */
  preview(): Promise<UsageReport | null>
  /** First try about two minutes after launch, then an hourly tick, and the first week's setup checks. */
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
  let dailyInFlight = false
  let setupInFlight: Promise<AttemptResult> | null = null
  let cancelNudge: (() => void) | null = null
  const stops: Array<() => void> = []

  const build = async (
    file: PrivacyFile,
    at: Date,
    trigger: ReportTrigger
  ): Promise<UsageReport | null> => {
    if (platform === null || os === null) return null
    const firstWeek = inFirstWeek(file.firstRunAt, at)
    const flags = trigger === "daily" ? activeFlags(file.lastReport, at) : NO_FLAGS
    const summary = await deps.summary(weekSince(file.firstRunAt, at))
    return buildUsageReport({
      appVersion,
      platform,
      os,
      firstRunAt: file.firstRunAt,
      trigger,
      flags,
      withHardware: carriesHardware({ trigger, flags, firstWeek, sent: file.hardwareSent }),
      withWeek: carriesWeek(trigger, flags, firstWeek),
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

  /**
   * "sent" only once the endpoint accepted it; "refused" is a 4xx answer, which
   * the same body would get again. `retry` says when the next try comes.
   */
  const post = async (
    body: UsageReport,
    retry: { failed: string; refused?: string }
  ): Promise<AttemptResult | "refused"> => {
    const what = `${body.trigger} usage report`
    const json = JSON.stringify(body)
    if (Buffer.byteLength(json) > MAX_BODY_BYTES) {
      log(`${what} not sent: over 4 KB`)
      return "failed"
    }
    // Asked again: the user may have said no while the summary was read.
    if (!allowed(deps.store.read())) {
      log(`${what} not sent: switched off while it was being built`)
      return "skipped"
    }
    try {
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
        const refused = reply.status >= 400 && reply.status < 500
        const next = (refused && retry.refused) || retry.failed
        log(`${what} to ${host} not accepted (HTTP ${reply.status}), ${next}`)
        return refused ? "refused" : "failed"
      }
      return "sent"
    } catch (error) {
      const reason = error instanceof Error && error.name === "TimeoutError" ? "timed out" : "unreachable"
      log(`${what} to ${host} ${reason}, ${retry.failed}`)
      return "failed"
    }
  }

  // What any accepted report leaves behind, daily or setup.
  const accepted = (file: PrivacyFile, body: UsageReport, at: Date): PrivacyFile => ({
    ...file,
    lastSent: { at: at.toISOString(), body },
    onboardingReported: furthestStep(file.onboardingReported, body.week?.onboarding),
    hardwareSent: sentHardware(body.hardware) ?? file.hardwareSent,
  })

  const attempt = async (): Promise<AttemptResult> => {
    // A setup report about to record a step goes first, so this one sees it.
    if (setupInFlight) await setupInFlight
    if (dailyInFlight) return "skipped"
    const file = deps.store.read()
    if (!allowed(file)) return "skipped"
    const at = now()
    if (reportedToday(file.lastReport, at)) return "skipped"
    const day = utcDay(at)
    const tries = file.attempts?.day === day ? file.attempts.count : 0
    if (tries >= MAX_ATTEMPTS_PER_DAY) return "skipped"
    deps.store.update((current) => ({ ...current, attempts: { day, count: tries + 1 } }))
    dailyInFlight = true
    try {
      const body = await build(file, at, "daily")
      if (body === null) return "skipped"
      const result = await post(body, { failed: `try ${tries + 1} of 3 today` })
      if (result !== "sent") return result === "refused" ? "failed" : result
      deps.store.update((current) => ({ ...accepted(current, body, at), lastReport: reportPeriod(at) }))
      log(`daily usage report sent to ${host}`)
      deps.onSent?.()
      return "sent"
    } catch (error) {
      log(`daily usage report not built: ${errorText(error)}`)
      return "failed"
    } finally {
      dailyInFlight = false
    }
  }

  const setupCheck = async (): Promise<AttemptResult> => {
    const file = deps.store.read()
    const at = now()
    if (!allowed(file) || !inFirstWeek(file.firstRunAt, at)) return "skipped"
    const body = await build(file, at, "setup")
    const step = setupStep(body?.week?.onboarding)
    const { onboardingReported, setupTries } = deps.store.read()
    if (
      body === null ||
      step === null ||
      !setupReportDue(step, onboardingReported) ||
      !setupTryAllowed(setupTries, step, at)
    ) {
      return "skipped"
    }
    const tries = countSetupTry(setupTries, step, at)
    deps.store.update((current) => ({ ...current, setupTries: tries }))
    const result = await post(body, {
      failed: `try ${tries.count} of 3 today for ${step}, an hour apart`,
      refused: `${step} not tried again today`,
    })
    if (result === "refused") {
      deps.store.update((current) => ({ ...current, setupTries: refusedSetupTry(step, at) }))
      return "failed"
    }
    if (result !== "sent") return result
    // Never lastReport or attempts: the daily report still goes today.
    deps.store.update((current) => accepted(current, body, at))
    log(`setup usage report sent to ${host}`)
    deps.onSent?.()
    return "sent"
  }

  const checkSetup = async (): Promise<AttemptResult> => {
    // The daily report in flight may carry the same step; the next check sees it.
    if (dailyInFlight || setupInFlight) return "skipped"
    setupInFlight = setupCheck()
      .catch((error: unknown): AttemptResult => {
        log(`setup usage report not built: ${errorText(error)}`)
        return "failed"
      })
      .finally(() => {
        setupInFlight = null
      })
    return setupInFlight
  }

  const tryDaily = () => void attempt()
  const tryBoth = () => void attempt().then(checkSetup)

  return {
    attempt,
    checkSetup,
    preview: async () => build(deps.store.read(), now(), "daily"),
    start() {
      stops.push(timers.after(tryBoth, FIRST_ATTEMPT_DELAY_MS))
      stops.push(timers.every(tryDaily, HOUR_MS))
      if (!inFirstWeek(deps.store.read().firstRunAt, now())) return
      const cancel = timers.every(() => {
        if (inFirstWeek(deps.store.read().firstRunAt, now())) void checkSetup()
        else cancel()
      }, SETUP_CHECK_MS)
      stops.push(cancel)
    },
    nudge() {
      cancelNudge?.()
      cancelNudge = timers.after(tryBoth, FIRST_ATTEMPT_DELAY_MS)
    },
    stop() {
      cancelNudge?.()
      for (const stop of stops.splice(0)) stop()
    },
  }
}
