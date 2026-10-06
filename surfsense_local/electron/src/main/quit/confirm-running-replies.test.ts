import assert from "node:assert/strict"
import test from "node:test"

import { confirmQuit } from "./confirm-running-replies.ts"

function deps(active: number, answer: boolean) {
  const calls: string[] = []
  return {
    calls,
    deps: {
      countRunning: async () => {
        calls.push("count")
        return active
      },
      ask: async (count: number) => {
        calls.push(`ask ${count}`)
        return answer
      },
      saveRunning: async () => {
        calls.push("save")
      },
    },
  }
}

test("quits without asking when no reply is being written", async () => {
  const { calls, deps: d } = deps(0, false)

  assert.equal(await confirmQuit(d), true)
  assert.deepEqual(calls, ["count"])
})

test("asks first, then saves every reply before the app goes", async () => {
  const { calls, deps: d } = deps(2, true)

  assert.equal(await confirmQuit(d), true)
  assert.deepEqual(calls, ["count", "ask 2", "save"])
})

test("stays open when the person cancels, saving nothing", async () => {
  const { calls, deps: d } = deps(1, false)

  assert.equal(await confirmQuit(d), false)
  assert.deepEqual(calls, ["count", "ask 1"])
})

test("an API that cannot be asked does not hold the quit", async () => {
  const quit = await confirmQuit({
    countRunning: async () => {
      throw new Error("refused")
    },
    ask: async () => assert.fail("nothing to ask about"),
    saveRunning: async () => assert.fail("nothing to save"),
  })

  assert.equal(quit, true)
})

test("a save that fails still lets the app quit", async () => {
  const quit = await confirmQuit({
    countRunning: async () => 1,
    ask: async () => true,
    saveRunning: async () => {
      throw new Error("timed out")
    },
  })

  assert.equal(quit, true)
})
