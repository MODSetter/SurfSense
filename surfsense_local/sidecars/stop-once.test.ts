import assert from "node:assert/strict"
import { test } from "node:test"

import { stopOnce } from "./stop-once.ts"

test("a stop asked for twice runs once", async () => {
  let runs = 0
  const stop = stopOnce(async () => {
    runs += 1
  })
  await Promise.all([stop(), stop()])
  await stop()
  assert.equal(runs, 1)
})

test("a second call while stopping waits for the first to finish, not returning at once", async () => {
  let finish!: () => void
  const stop = stopOnce(() => new Promise<void>((resolve) => (finish = resolve)))
  const first = stop()
  let secondDone = false
  const second = stop().then(() => {
    secondDone = true
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(secondDone, false)
  finish()
  await Promise.all([first, second])
  assert.equal(secondDone, true)
})
