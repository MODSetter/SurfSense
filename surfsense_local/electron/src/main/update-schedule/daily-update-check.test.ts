import assert from "node:assert/strict"
import test from "node:test"

import { scheduleDailyUpdateCheck } from "./daily-update-check.ts"

type Outcome = "manifest" | "nothing" | "pending"

/** The schedule on a clock the test moves, with the hourly tick in its hands. */
function schedule(options: {
  automatic?: boolean
  lastAutomaticDay?: string
  at: string
  outcomes?: Outcome[]
}) {
  let clock = new Date(options.at)
  let lastAutomaticDay = options.lastAutomaticDay
  let automatic = options.automatic ?? true
  const outcomes = [...(options.outcomes ?? [])]
  let tick: (() => Promise<boolean>) | null = null
  let tickEvery = 0
  let checks = 0
  let finish = () => undefined as void
  const daily = scheduleDailyUpdateCheck({
    automatic: () => automatic,
    lastAutomaticDay: () => lastAutomaticDay,
    markAutomaticDay: (day) => (lastAutomaticDay = day),
    check: () => {
      checks += 1
      const outcome = outcomes.shift() ?? "manifest"
      if (outcome === "pending") {
        return new Promise<boolean>((resolve) => (finish = () => resolve(true)))
      }
      return Promise.resolve(outcome === "manifest")
    },
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
    tick: async () => void (await tick?.()),
    finish: () => finish(),
  }
}

/** Lets the launch check's answer arrive. */
const settle = () => new Promise((resolve) => setImmediate(resolve))

test("checks at launch when no automatic check ran this UTC day", async () => {
  const app = schedule({ lastAutomaticDay: "2026-10-20", at: "2026-10-21T08:00:00Z" })
  await settle()

  assert.equal(app.checks(), 1)
  assert.equal(app.lastAutomaticDay(), "2026-10-21")
})

test("a second launch on the same UTC day does not check again", () => {
  const app = schedule({ lastAutomaticDay: "2026-10-21", at: "2026-10-21T23:59:00Z" })

  assert.equal(app.checks(), 0)
})

test("an hourly tick checks once the UTC day turns while the app is open", async () => {
  const app = schedule({ at: "2026-10-21T22:30:00Z" })
  await settle()
  assert.equal(app.tickEvery(), 3_600_000)
  assert.equal(app.checks(), 1)

  app.at("2026-10-21T23:30:00Z")
  await app.tick()
  assert.equal(app.checks(), 1)

  app.at("2026-10-22T00:30:00Z")
  await app.tick()
  app.at("2026-10-22T01:30:00Z")
  await app.tick()
  assert.equal(app.checks(), 2)
})

test("a launch check that reads no manifest is tried again on the next tick", async () => {
  const app = schedule({ at: "2026-10-21T08:00:00Z", outcomes: ["nothing", "manifest"] })
  await settle()
  assert.equal(app.checks(), 1)
  assert.equal(app.lastAutomaticDay(), undefined)

  app.at("2026-10-21T09:00:00Z")
  await app.tick()
  assert.equal(app.checks(), 2)
  assert.equal(app.lastAutomaticDay(), "2026-10-21")

  app.at("2026-10-21T10:00:00Z")
  await app.tick()
  assert.equal(app.checks(), 2)
})

test("three tries a UTC day while no manifest can be read, then again the next day", async () => {
  const app = schedule({
    at: "2026-10-21T08:00:00Z",
    outcomes: ["nothing", "nothing", "nothing", "nothing", "manifest"],
  })
  await settle()

  for (const hour of ["09", "10", "11", "12"]) {
    app.at(`2026-10-21T${hour}:00:00Z`)
    await app.tick()
  }
  assert.equal(app.checks(), 3)
  assert.equal(app.lastAutomaticDay(), undefined)

  app.at("2026-10-22T00:30:00Z")
  await app.tick()
  assert.equal(app.checks(), 4)
})

test("a tick while the check is still running does not start another", async () => {
  const app = schedule({ at: "2026-10-21T08:00:00Z", outcomes: ["pending"] })

  app.at("2026-10-21T09:00:00Z")
  await app.tick()
  assert.equal(app.checks(), 1)

  app.finish()
  await settle()
  assert.equal(app.lastAutomaticDay(), "2026-10-21")
})

test("nothing runs while automatic checks are off, and turning them on starts the day's check", async () => {
  const app = schedule({ automatic: false, at: "2026-10-21T08:00:00Z" })
  await app.tick()
  assert.equal(app.checks(), 0)

  app.turn(true)
  await app.tick()
  assert.equal(app.checks(), 1)
})

test("stop ends the hourly tick", async () => {
  const app = schedule({ automatic: false, at: "2026-10-21T08:00:00Z" })
  app.daily.stop()
  app.turn(true)
  await app.tick()
  assert.equal(app.checks(), 0)
})
