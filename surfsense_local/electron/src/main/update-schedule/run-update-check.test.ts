import assert from "node:assert/strict"
import test from "node:test"

import type { UpdatePrefs } from "../updater.ts"
import { updateCheckRunner } from "./run-update-check.ts"

function runner(locked: boolean, prefs: UpdatePrefs) {
  let stored = prefs
  let checks = 0
  const run = updateCheckRunner({
    locked,
    updates: { check: async () => void (checks += 1) },
    readPrefs: () => stored,
    writePrefs: (next) => (stored = next),
    now: () => new Date("2026-10-21T09:00:00Z"),
  })
  return { run, checks: () => checks, prefs: () => stored }
}

test("Check now always runs, even after today's automatic check, and is stamped as the last call", () => {
  const app = runner(false, { automatic: true, lastAutomaticDay: "2026-10-21" })

  assert.equal(app.run("manual"), true)
  assert.equal(app.run("manual"), true)

  assert.equal(app.checks(), 2)
  assert.deepEqual(app.prefs(), {
    automatic: true,
    lastAutomaticDay: "2026-10-21",
    lastCheckedAt: "2026-10-21T09:00:00.000Z",
  })
})

test("a policy that turns updates off stops every check, Check now included", () => {
  const app = runner(true, { automatic: true })

  assert.equal(app.run("manual"), false)
  assert.equal(app.run("automatic"), false)

  assert.equal(app.checks(), 0)
  assert.deepEqual(app.prefs(), { automatic: true })
})
