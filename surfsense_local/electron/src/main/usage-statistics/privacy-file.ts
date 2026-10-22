import { readFileSync, renameSync, writeFileSync } from "node:fs"

/** The UTC day, ISO week and month of the last report that was accepted. */
export type ReportPeriod = { day: string; week: string; month: string }

/**
 * userData/privacy.json (contract 05, part C). `attempts` is local only: the
 * contract allows three tries per UTC day, across restarts too.
 */
export type PrivacyFile = {
  /** null: never asked. */
  usageStatistics: boolean | null
  firstRunAt: string
  firstRunAsked: boolean
  lastReport: ReportPeriod | null
  lastSent: { at: string; body: object } | null
  attempts: { day: string; count: number } | null
}

export type PrivacyStore = {
  read(): PrivacyFile
  update(change: (file: PrivacyFile) => PrivacyFile): PrivacyFile
}

const DAY = /^\d{4}-\d{2}-\d{2}$/
const WEEK = /^\d{4}-W\d{2}$/
const MONTH = /^\d{4}-\d{2}$/

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function isoTime(value: unknown): string | null {
  return typeof value === "string" && !Number.isNaN(Date.parse(value)) ? value : null
}

function reportPeriod(value: unknown): ReportPeriod | null {
  const period = record(value)
  if (!period) return null
  const { day, week, month } = period
  return typeof day === "string" &&
    DAY.test(day) &&
    typeof week === "string" &&
    WEEK.test(week) &&
    typeof month === "string" &&
    MONTH.test(month)
    ? { day, week, month }
    : null
}

/** What was on disk, with anything unreadable taken as never set. */
export function parsePrivacyFile(value: unknown, now: Date): PrivacyFile {
  const file = record(value) ?? {}
  const lastSent = record(file.lastSent)
  const attempts = record(file.attempts)
  return {
    usageStatistics: typeof file.usageStatistics === "boolean" ? file.usageStatistics : null,
    firstRunAt: isoTime(file.firstRunAt) ?? now.toISOString(),
    firstRunAsked: file.firstRunAsked === true,
    lastReport: reportPeriod(file.lastReport),
    lastSent:
      lastSent && isoTime(lastSent.at) && record(lastSent.body)
        ? { at: lastSent.at as string, body: lastSent.body as object }
        : null,
    attempts:
      attempts &&
      typeof attempts.day === "string" &&
      DAY.test(attempts.day) &&
      Number.isInteger(attempts.count)
        ? { day: attempts.day, count: attempts.count as number }
        : null,
  }
}

function readJson(path: string): unknown {
  try {
    return JSON.parse(readFileSync(path, "utf8"))
  } catch {
    return undefined
  }
}

function write(path: string, file: PrivacyFile): void {
  writeFileSync(`${path}.tmp`, JSON.stringify(file))
  renameSync(`${path}.tmp`, path)
}

/**
 * The file at `path`; the first read stamps firstRunAt, which install_week comes
 * from. A failed write keeps the change in memory: privacy must never stop the app.
 */
export function privacyStore(
  path: string,
  options: { now?: () => Date; onWriteError?: (error: unknown) => void } = {}
): PrivacyStore {
  const { now = () => new Date(), onWriteError = () => undefined } = options
  const save = (file: PrivacyFile) => {
    try {
      write(path, file)
    } catch (error) {
      onWriteError(error)
    }
  }
  const raw = readJson(path)
  let current = parsePrivacyFile(raw, now())
  if (isoTime(record(raw)?.firstRunAt) === null) save(current)
  return {
    read: () => current,
    update(change) {
      current = change(current)
      save(current)
      return current
    },
  }
}
