import { isoWeek, utcDay, utcMonth } from "../utc-calendar.ts"
import type { ReportPeriod } from "./privacy-file.ts"

/** Brave-style activity flags: what an ID would otherwise count, with no ID. */
export type ActiveFlags = { first: boolean; week: boolean; month: boolean }

export function reportPeriod(now: Date): ReportPeriod {
  return { day: utcDay(now), week: isoWeek(now), month: utcMonth(now) }
}

export function reportedToday(last: ReportPeriod | null, now: Date): boolean {
  return last !== null && last.day === utcDay(now)
}

/** first: no report ever; week: none this ISO week; month: none this UTC calendar month. */
export function activeFlags(last: ReportPeriod | null, now: Date): ActiveFlags {
  const period = reportPeriod(now)
  return {
    first: last === null,
    week: last === null || last.week !== period.week,
    month: last === null || last.month !== period.month,
  }
}
