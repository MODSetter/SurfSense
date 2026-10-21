import assert from "node:assert/strict"
import test from "node:test"

import { parseGoBackResult, parseGoingBackOptions } from "./backend-commands.ts"

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

test("an answer it cannot read is no answer, not an empty one", () => {
  assert.equal(parseGoingBackOptions("Traceback (most recent call last)"), null)
})

test("going back that exits cleanly went back", () => {
  assert.equal(parseGoBackResult({ exitCode: 0, stdout: "" }), "went-back")
})

test("a failure is unchanged only when the backend says so", () => {
  assert.equal(
    parseGoBackResult({ exitCode: 1, stdout: '{"data_unchanged": true}' }),
    "failed-data-unchanged",
  )
  assert.equal(
    parseGoBackResult({ exitCode: 1, stdout: '{"data_unchanged": false}' }),
    "failed-data-may-have-changed",
  )
})

test("a backend killed partway may have changed the data", () => {
  assert.equal(parseGoBackResult({ exitCode: null, stdout: "" }), "failed-data-may-have-changed")
})
