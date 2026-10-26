import { readFileSync, renameSync, writeFileSync } from "node:fs"

import { setupStep, type SetupStep } from "./setup-progress.ts"
import { parseSetupTries, type SetupTries } from "./setup-tries.ts"

/** The UTC day, ISO week and month of the last report that was accepted. */
export type ReportPeriod = { day: string; week: string; month: string }

/** The GPU half of the last hardware block sent; gpu_runtime null: sent before it existed. */
export type SentHardware = { gpu: string; vram_gb: string; gpu_runtime: string | null }

/**
 * userData/privacy.json (contract 05, part C). `attempts`, `onboardingReported`,
 * `hardwareSent` and `setupTries` are local only: the daily and setup reports'
 * tries across restarts, and what decides the first week's setup reports and hardware.
 */
export type PrivacyFile = {
  /** null: never asked. */
  usageStatistics: boolean | null
  firstRunAt: string
  firstRunAsked: boolean
  lastReport: ReportPeriod | null
  lastSent: { at: string; body: object } | null
  attempts: { day: string; count: number } | null
  /** The furthest setup step any accepted report carried. */
  onboardingReported: SetupStep | null
  hardwareSent: SentHardware | null
  setupTries: SetupTries | null
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

/** What a hardware block leaves to remember, or null when there is none. */
export function sentHardware(value: unknown): SentHardware | null {
  const hardware = record(value)
  if (!hardware || typeof hardware.gpu !== "string" || typeof hardware.vram_gb !== "string") return null
  const runtime = hardware.gpu_runtime
  return {
    gpu: hardware.gpu,
    vram_gb: hardware.vram_gb,
    gpu_runtime: typeof runtime === "string" ? runtime : null,
  }
}

/**
 * What was on disk, with anything unreadable taken as never set. A file written
 * before the last two fields existed has only its last report to say what was carried.
 */
export function parsePrivacyFile(value: unknown, now: Date): PrivacyFile {
  const file = record(value) ?? {}
  const lastSent = record(file.lastSent)
  const attempts = record(file.attempts)
  const lastBody = record(lastSent?.body)
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
    onboardingReported:
      setupStep(file.onboardingReported) ?? setupStep(record(lastBody?.week)?.onboarding),
    hardwareSent: sentHardware(file.hardwareSent) ?? sentHardware(lastBody?.hardware),
    setupTries: parseSetupTries(file.setupTries),
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
