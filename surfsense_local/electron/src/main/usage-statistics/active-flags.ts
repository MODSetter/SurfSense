import { isoWeek, utcDay, utcMonth } from "../utc-calendar.ts"
import { installAge, laterAge } from "./install-age.ts"
import type { ReportPeriod } from "./privacy-file.ts"

/** Brave-style activity flags: what an ID would otherwise count, with no ID. */
export type ActiveFlags = { first: boolean; week: boolean; month: boolean; age: boolean }

export function reportPeriod(now: Date): Omit<ReportPeriod, "age"> {
  return { day: utcDay(now), week: isoWeek(now), month: utcMonth(now) }
}

export function reportedToday(last: ReportPeriod | null, now: Date): boolean {
  return last !== null && last.day === utcDay(now)
}

/**
 * first: no report ever; week: none this ISO week; month: none this UTC calendar
 * month; age (revision 1.2): none yet in this install_age range or a later one,
 * so a clock set back and restored never says a range is new twice. A report
 * from before 1.2 kept no range, so the first 1.2 report says its range is new.
 */
export function activeFlags(last: ReportPeriod | null, now: Date, firstRunAt: string): ActiveFlags {
  const period = reportPeriod(now)
  return {
    first: last === null,
    week: last === null || last.week !== period.week,
    month: last === null || last.month !== period.month,
    age: last === null || laterAge(last.age, installAge(firstRunAt, now)) !== last.age,
  }
}
