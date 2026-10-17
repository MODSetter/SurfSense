import assert from "node:assert/strict"
import test from "node:test"

import {
  offerGoingBack,
  type GoingBackOptions,
  type Question,
  type Way,
} from "./offer-going-back.ts"

const SAVED_AT = new Date("2026-10-14T07:30:00Z")

function fakes(
  options: GoingBackOptions,
  { answers = [], fails = [] }: { answers?: boolean[]; fails?: Way[] } = {},
) {
  const asked: Question[] = []
  const ran: Way[] = []
  return {
    asked,
    ran,
    deps: {
      options: async () => options,
      goBack: async (way: Way) => {
        ran.push(way)
        return !fails.includes(way)
      },
      ask: async (question: Question) => {
        asked.push(question)
        return question.kind === "cannot-go-back" ? false : (answers.shift() ?? false)
      },
    },
  }
}

test("with the newer release's undo steps, it offers to change the data back", async () => {
  const fake = fakes({ canUndo: true, backupSavedAt: SAVED_AT }, { answers: [true] })

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.asked, [{ kind: "undo" }])
  assert.deepEqual(fake.ran, ["undo"])
  assert.equal(outcome, "restart")
})

test("without them, it offers the copy from before the update", async () => {
  const fake = fakes({ canUndo: false, backupSavedAt: SAVED_AT }, { answers: [true] })

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.asked, [{ kind: "restore", savedAt: SAVED_AT, afterFailedUndo: false }])
  assert.deepEqual(fake.ran, ["restore"])
  assert.equal(outcome, "restart")
})

test("with neither, it says to install the newer release again", async () => {
  const fake = fakes({ canUndo: false, backupSavedAt: null })

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.asked, [{ kind: "cannot-go-back", reason: "nothing-to-go-back-to" }])
  assert.deepEqual(fake.ran, [])
  assert.equal(outcome, "quit")
})

test("quitting at the question changes nothing", async () => {
  const fake = fakes({ canUndo: true, backupSavedAt: SAVED_AT }, { answers: [false] })

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.ran, [])
  assert.equal(outcome, "quit")
})

test("an undo that fails falls back to offering the copy", async () => {
  const fake = fakes(
    { canUndo: true, backupSavedAt: SAVED_AT },
    { answers: [true, true], fails: ["undo"] },
  )

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.asked, [
    { kind: "undo" },
    { kind: "restore", savedAt: SAVED_AT, afterFailedUndo: true },
  ])
  assert.deepEqual(fake.ran, ["undo", "restore"])
  assert.equal(outcome, "restart")
})

test("going back that fails with nothing left to try says so and quits", async () => {
  const fake = fakes(
    { canUndo: false, backupSavedAt: SAVED_AT },
    { answers: [true], fails: ["restore"] },
  )

  const outcome = await offerGoingBack(fake.deps)

  assert.deepEqual(fake.asked.at(-1), { kind: "cannot-go-back", reason: "going-back-failed" })
  assert.equal(outcome, "quit")
})
