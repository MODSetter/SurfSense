import assert from "node:assert/strict"
import test from "node:test"

import { scheduleDailyUpdateCheck } from "./daily-update-check.ts"

/** The schedule on a clock the test moves, with the hourly tick in its hands. */
function schedule(options: { automatic?: boolean; lastAutomaticDay?: string; at: string }) {
  let clock = new Date(options.at)
  let lastAutomaticDay = options.lastAutomaticDay
  let automatic = options.automatic ?? true
  let tick: (() => void) | null = null
  let tickEvery = 0
  let checks = 0
  const daily = scheduleDailyUpdateCheck({
    automatic: () => automatic,
    lastAutomaticDay: () => lastAutomaticDay,
    markAutomaticDay: (day) => (lastAutomaticDay = day),
    check: () => (checks += 1),
    now: () => clock,
    every: (run, ms) => {
      tick = run
      tickEvery = ms
      return () => (tick = null)
    },
  })
  return {
    daily,
    checks: () => checks,
    tickEvery: () => tickEvery,
    lastAutomaticDay: () => lastAutomaticDay,
    at: (iso: string) => (clock = new Date(iso)),
    turn: (on: boolean) => (automatic = on),
    tick: () => tick?.(),
  }
}

test("checks at launch when no automatic check ran this UTC day", () => {
  const app = schedule({ lastAutomaticDay: "2026-10-20", at: "2026-10-21T08:00:00Z" })

  assert.equal(app.checks(), 1)
  assert.equal(app.lastAutomaticDay(), "2026-10-21")
})

test("a second launch on the same UTC day does not check again", () => {
  const app = schedule({ lastAutomaticDay: "2026-10-21", at: "2026-10-21T23:59:00Z" })

  assert.equal(app.checks(), 0)
})

test("an hourly tick checks once the UTC day turns while the app is open", () => {
  const app = schedule({ at: "2026-10-21T22:30:00Z" })
  assert.equal(app.tickEvery(), 3_600_000)
  assert.equal(app.checks(), 1)

  app.at("2026-10-21T23:30:00Z")
  app.tick()
  assert.equal(app.checks(), 1)

  app.at("2026-10-22T00:30:00Z")
  app.tick()
  app.at("2026-10-22T01:30:00Z")
  app.tick()
  assert.equal(app.checks(), 2)
})

test("nothing runs while automatic checks are off, and turning them on starts the day's check", () => {
  const app = schedule({ automatic: false, at: "2026-10-21T08:00:00Z" })
  app.tick()
  assert.equal(app.checks(), 0)

  app.turn(true)
  app.tick()
  assert.equal(app.checks(), 1)
})

test("stop ends the hourly tick", () => {
  const app = schedule({ automatic: false, at: "2026-10-21T08:00:00Z" })
  app.daily.stop()
  app.turn(true)
  app.tick()
  assert.equal(app.checks(), 0)
})
