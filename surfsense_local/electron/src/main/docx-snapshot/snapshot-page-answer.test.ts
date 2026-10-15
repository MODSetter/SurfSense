import assert from "node:assert/strict"
import test from "node:test"

import { snapshotPageFailure } from "./snapshot-page-answer.ts"

test("a laid-out page has no failure", () => {
  assert.equal(snapshotPageFailure(null, []), null)
})

test("the page's own reason is passed on as it is", () => {
  assert.equal(
    snapshotPageFailure("the Word file could not be fetched (HTTP 404)", ["ignored"]),
    "the Word file could not be fetched (HTTP 404)",
  )
})

test("a page whose script never ran says so, with the window's first error", () => {
  assert.equal(
    snapshotPageFailure(undefined, [
      "Failed to load module script: assets/docx-snapshot-a1.js",
      "second error",
    ]),
    "the snapshot page did not start (its script did not load): " +
      "Failed to load module script: assets/docx-snapshot-a1.js",
  )
  assert.equal(
    snapshotPageFailure(undefined, []),
    "the snapshot page did not start (its script did not load)",
  )
})
