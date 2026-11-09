// Calendar labels in UTC, so a day, week or month means the same everywhere:
// update checks and usage reports count at most one per UTC day.

const DAY_MS = 86_400_000

/** "2026-10-21" */
export function utcDay(date: Date): string {
  return date.toISOString().slice(0, 10)
}

/** "2026-10" */
export function utcMonth(date: Date): string {
  return date.toISOString().slice(0, 7)
}

/** ISO 8601 week, "2026-W43": weeks start on Monday and belong to the year of their Thursday. */
export function isoWeek(date: Date): string {
  const day = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
  const weekday = new Date(day).getUTCDay() || 7
  const thursday = new Date(day + (4 - weekday) * DAY_MS)
  const year = thursday.getUTCFullYear()
  const week = Math.floor((thursday.getTime() - Date.UTC(year, 0, 1)) / DAY_MS / 7) + 1
  return `${year}-W${String(week).padStart(2, "0")}`
}
