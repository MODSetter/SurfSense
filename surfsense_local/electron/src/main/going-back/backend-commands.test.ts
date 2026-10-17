import assert from "node:assert/strict"
import test from "node:test"

import { parseGoingBackOptions } from "./backend-commands.ts"

test("the backend's options are read with the backup's date", () => {
  const options = parseGoingBackOptions(
    '{"can_undo": true, "backup_saved_at": "2026-10-14T07:30:00+00:00"}',
  )

  assert.deepEqual(options, {
    canUndo: true,
    backupSavedAt: new Date("2026-10-14T07:30:00Z"),
  })
})

test("no backup reads as none", () => {
  assert.deepEqual(parseGoingBackOptions('{"can_undo": false, "backup_saved_at": null}'), {
    canUndo: false,
    backupSavedAt: null,
  })
})

test("an answer it cannot read offers nothing rather than guessing", () => {
  assert.deepEqual(parseGoingBackOptions("Traceback (most recent call last)"), {
    canUndo: false,
    backupSavedAt: null,
  })
})
