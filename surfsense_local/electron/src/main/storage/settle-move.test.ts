import assert from "node:assert/strict"
import test from "node:test"

import { MoveFailedError } from "./run-move.ts"
import { settleMove } from "./settle-move.ts"

function recorder() {
  const steps: string[] = []
  return {
    steps,
    onMovingChange: (moving: boolean) => steps.push(`moving:${moving}`),
    restart: () => steps.push("restart"),
    onFailed: (reason: string) => steps.push(`failed:${reason}`),
  }
}

test("a finished move stops holding the window before it restarts, or the quit is refused", async () => {
  const r = recorder()
  await settleMove(Promise.resolve(), r)
  assert.deepEqual(r.steps, ["moving:false", "restart"])
})

test("a cancelled move restarts on the folder it never left, with nothing to say", async () => {
  const r = recorder()
  await settleMove(Promise.reject(new MoveFailedError("canceled")), r)
  assert.deepEqual(r.steps, ["moving:false", "restart"])
})

test("a failed move waits for the user, who is told why", async () => {
  const r = recorder()
  await settleMove(Promise.reject(new MoveFailedError("no_room")), r)
  assert.deepEqual(r.steps, ["moving:false", "failed:no_room"])
})

test("an error that is not the mover's own still reports a failure", async () => {
  const r = recorder()
  await settleMove(Promise.reject(new Error("surprise")), r)
  assert.deepEqual(r.steps, ["moving:false", "failed:failed"])
})
