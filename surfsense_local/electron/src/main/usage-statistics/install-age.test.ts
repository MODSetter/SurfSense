import assert from "node:assert/strict"
import test from "node:test"

import { INSTALL_AGES, installAge } from "./install-age.ts"

const FIRST_RUN = "2026-10-20T08:00:00.000Z"

/** The report's time, `days` UTC days after the first run's day, at noon. */
function after(days: number): Date {
  return new Date(Date.UTC(2026, 9, 20 + days, 12))
}

test("each range starts on the contract's day, and a range is whole days of UTC", () => {
  const starts = [0, 1, 2, 4, 8, 15, 31, 61].map((days) => installAge(FIRST_RUN, after(days)))
  const ends = [0, 1, 3, 7, 14, 30, 60, 400].map((days) => installAge(FIRST_RUN, after(days)))

  assert.deepEqual(starts, [...INSTALL_AGES])
  assert.deepEqual(ends, [...INSTALL_AGES])
})

test("the day turns at UTC midnight, not 24 hours after the first run", () => {
  assert.equal(installAge("2026-10-20T23:30:00Z", new Date("2026-10-21T00:10:00Z")), "1")
  assert.equal(installAge("2026-10-20T00:10:00Z", new Date("2026-10-20T23:50:00Z")), "0")
})

test("a clock set back before the first run reads as day 0", () => {
  assert.equal(installAge(FIRST_RUN, new Date("2026-10-18T09:00:00Z")), "0")
})
