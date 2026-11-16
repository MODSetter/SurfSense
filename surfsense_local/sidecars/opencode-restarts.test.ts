import assert from "node:assert/strict"
import test from "node:test"

import { OpencodeRestarts } from "./opencode-restarts.ts"

const SECOND = 1000

test("a quick exit restarts opencode after 10 s, then 20 s", () => {
  const restarts = new OpencodeRestarts()

  restarts.started(0)
  assert.deepEqual(restarts.exited(2 * SECOND, "code 1"), { restartInMs: 10 * SECOND })
  assert.equal(restarts.mayStart(11 * SECOND, 0), false)
  assert.equal(restarts.mayStart(12 * SECOND, 0), true)

  restarts.started(12 * SECOND)
  assert.deepEqual(restarts.exited(14 * SECOND, "code 1"), { restartInMs: 20 * SECOND })
  assert.equal(restarts.mayStart(33 * SECOND, 0), false)
  assert.equal(restarts.mayStart(34 * SECOND, 0), true)
})

test("the third quick exit in a row gives up, with its reason", () => {
  const restarts = new OpencodeRestarts()

  restarts.started(0)
  restarts.exited(1 * SECOND, "code 1")
  restarts.started(11 * SECOND)
  restarts.exited(12 * SECOND, "code 1")
  restarts.started(32 * SECOND)

  assert.deepEqual(restarts.exited(33 * SECOND, "code 7"), { gaveUp: "code 7" })
  assert.equal(restarts.mayStart(3600 * SECOND, 0), false)
})

test("a run that stayed up starts the count again", () => {
  const restarts = new OpencodeRestarts()

  restarts.started(0)
  restarts.exited(1 * SECOND, "code 1")
  restarts.started(11 * SECOND)
  restarts.exited(12 * SECOND, "code 1")
  restarts.started(32 * SECOND)

  assert.deepEqual(restarts.exited(600 * SECOND, "code 1"), { restartInMs: 10 * SECOND })
})

test("after giving up, the API asking again earns one more try", () => {
  const restarts = new OpencodeRestarts()
  restarts.started(0)
  restarts.exited(1 * SECOND, "code 1")
  restarts.started(11 * SECOND)
  restarts.exited(12 * SECOND, "code 1")
  restarts.started(32 * SECOND)
  restarts.exited(33 * SECOND, "code 1")

  assert.equal(restarts.mayStart(40 * SECOND, 20 * SECOND), false)
  assert.equal(restarts.mayStart(50 * SECOND, 45 * SECOND), true)
  restarts.started(50 * SECOND)
  assert.deepEqual(restarts.exited(51 * SECOND, "code 1"), { gaveUp: "code 1" })
})
