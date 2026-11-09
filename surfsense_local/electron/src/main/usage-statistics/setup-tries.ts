import { utcDay } from "../utc-calendar.ts"
import { setupStep, type SetupStep } from "./setup-progress.ts"

// The setup report's own cap, so a 5-minute check never turns an outage into
// a stream of POSTs: three tries per step per UTC day, an hour apart, as the
// daily report gets.
const MAX_TRIES_PER_DAY = 3
const HOUR_MS = 3_600_000

/** The step the last setup report tried, when, and how many tries it had that UTC day. */
export type SetupTries = { step: SetupStep; at: string; count: number }

/** What privacy.json held, or null when it is not a record of tries. */
export function parseSetupTries(value: unknown): SetupTries | null {
  if (typeof value !== "object" || value === null) return null
  const { step, at, count } = value as Record<string, unknown>
  const known = setupStep(step)
  return known && typeof at === "string" && !Number.isNaN(Date.parse(at)) && Number.isInteger(count)
    ? { step: known, at, count: count as number }
    : null
}

function sameDay(tries: SetupTries, step: SetupStep, at: Date): boolean {
  return tries.step === step && utcDay(new Date(tries.at)) === utcDay(at)
}

/** A later step, or a new UTC day, starts with a full budget. */
export function setupTryAllowed(tries: SetupTries | null, step: SetupStep, at: Date): boolean {
  if (tries === null || !sameDay(tries, step, at)) return true
  return tries.count < MAX_TRIES_PER_DAY && at.getTime() - Date.parse(tries.at) >= HOUR_MS
}

/** Counted before the POST, so a try that never returns still counts. */
export function countSetupTry(tries: SetupTries | null, step: SetupStep, at: Date): SetupTries {
  const count = tries !== null && sameDay(tries, step, at) ? tries.count + 1 : 1
  return { step, at: at.toISOString(), count }
}

/** A 4xx would refuse the same body again, so the step waits for the next UTC day. */
export function refusedSetupTry(step: SetupStep, at: Date): SetupTries {
  return { step, at: at.toISOString(), count: MAX_TRIES_PER_DAY }
}
