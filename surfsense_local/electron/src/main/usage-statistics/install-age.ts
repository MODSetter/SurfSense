// Contract 05, revision 1.2: how many UTC days after firstRunAt a report goes,
// in ranges, so a cohort's retention reads by day with no ID.

const DAY_MS = 86_400_000

export const INSTALL_AGES = ["0", "1", "2-3", "4-7", "8-14", "15-30", "31-60", "61+"] as const

export type InstallAge = (typeof INSTALL_AGES)[number]

// The first day of each range after "0", in the order of INSTALL_AGES.
const STARTS: ReadonlyArray<readonly [number, InstallAge]> = [
  [61, "61+"],
  [31, "31-60"],
  [15, "15-30"],
  [8, "8-14"],
  [4, "4-7"],
  [2, "2-3"],
  [1, "1"],
]

function utcMidnight(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
}

/** Whole UTC days from firstRunAt's day to `at`'s day; a clock set back reads as day 0. */
export function installAge(firstRunAt: string, at: Date): InstallAge {
  const days = Math.max(0, Math.round((utcMidnight(at) - utcMidnight(new Date(firstRunAt))) / DAY_MS))
  return STARTS.find(([start]) => days >= start)?.[1] ?? "0"
}
