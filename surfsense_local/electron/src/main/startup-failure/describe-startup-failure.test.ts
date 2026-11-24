import assert from "node:assert/strict"
import test from "node:test"

import { describeStartupFailure } from "./describe-startup-failure.ts"

test("names why startup failed", () => {
  const { title, detail } = describeStartupFailure(
    new Error("sidecar exited during startup"),
    []
  )

  assert.equal(title, "SurfSense could not start")
  assert.match(detail, /^sidecar exited during startup/)
})

test("quotes the end of the API's output, where a failed migration is named", () => {
  const { detail } = describeStartupFailure(new Error("sidecar exited during startup"), [
    "10:00:00 [api] Traceback (most recent call last):",
    '10:00:00 [api]   File "main.py", line 5, in lifespan',
    '10:00:00 [api]   File "migrations.py", line 30, in upgrade_to_head',
    '10:00:00 [api]   File "migration_snapshot.py", line 36, in snapshot_before_upgrade',
    "10:00:00 [llamacpp] loading model",
    "10:00:00 [api] RuntimeError: could not write a database snapshot to ~/backups/0030-0032.db before migrating: database or disk is full",
  ])

  assert.match(detail, /RuntimeError: could not write a database snapshot/)
  assert.match(detail, /line 36, in snapshot_before_upgrade/)
  assert.doesNotMatch(detail, /llamacpp|\[api\]/)
  assert.doesNotMatch(detail, /Traceback/)
})

test("says nothing about the API when it wrote nothing", () => {
  const { detail } = describeStartupFailure("boom", ["10:00:00 [llamacpp] hi"])

  assert.match(detail, /^boom/)
  assert.doesNotMatch(detail, /last output/)
})
