import assert from "node:assert/strict"
import test from "node:test"

import type { UpdatePrefs } from "../updater.ts"
import { updateCheckRunner } from "./run-update-check.ts"

function runner(locked: boolean, prefs: UpdatePrefs, readsManifest = true) {
  let stored = prefs
  let checks = 0
  const run = updateCheckRunner({
    locked,
    updates: {
      check: async () => {
        checks += 1
        return readsManifest
      },
    },
    readPrefs: () => stored,
    writePrefs: (next) => (stored = next),
    now: () => new Date("2026-10-21T09:00:00Z"),
  })
  return { run, checks: () => checks, prefs: () => stored }
}

test("Check now always runs, even after today's automatic check, and is stamped as the last call", async () => {
  const app = runner(false, { automatic: true, lastAutomaticDay: "2026-10-21" })

  assert.equal(await app.run("manual"), true)
  assert.equal(await app.run("manual"), true)

  assert.equal(app.checks(), 2)
  assert.deepEqual(app.prefs(), {
    automatic: true,
    lastAutomaticDay: "2026-10-21",
    lastCheckedAt: "2026-10-21T09:00:00.000Z",
  })
})

test("a check that reads no manifest is still stamped as the last call", async () => {
  const app = runner(false, { automatic: true }, false)

  assert.equal(await app.run("automatic"), false)

  assert.equal(app.checks(), 1)
  assert.equal(app.prefs().lastCheckedAt, "2026-10-21T09:00:00.000Z")
})

test("a policy that turns updates off stops every check, Check now included", async () => {
  const app = runner(true, { automatic: true })

  assert.equal(await app.run("manual"), false)
  assert.equal(await app.run("automatic"), false)

  assert.equal(app.checks(), 0)
  assert.deepEqual(app.prefs(), { automatic: true })
})
