import assert from "node:assert/strict"
import test from "node:test"

import { isoWeek, utcDay, utcMonth } from "./utc-calendar.ts"

test("days and months are UTC's, whatever the local clock says", () => {
  const lateEvening = new Date("2026-10-31T23:30:00-05:00")
  assert.equal(utcDay(lateEvening), "2026-11-01")
  assert.equal(utcMonth(lateEvening), "2026-11")
})

test("ISO weeks start on Monday and belong to the year of their Thursday", () => {
  assert.equal(isoWeek(new Date("2026-10-21T12:00:00Z")), "2026-W43")
  assert.equal(isoWeek(new Date("2026-10-25T23:59:59Z")), "2026-W43")
  assert.equal(isoWeek(new Date("2026-10-26T00:00:00Z")), "2026-W44")
  // 2026 starts on a Thursday, so it has 53 weeks and 1 Jan 2027 is in its last.
  assert.equal(isoWeek(new Date("2026-01-01T00:00:00Z")), "2026-W01")
  assert.equal(isoWeek(new Date("2027-01-01T00:00:00Z")), "2026-W53")
  assert.equal(isoWeek(new Date("2027-01-04T00:00:00Z")), "2027-W01")
  // 29 Dec 2025 is a Monday whose Thursday is in 2026.
  assert.equal(isoWeek(new Date("2025-12-29T00:00:00Z")), "2026-W01")
})
