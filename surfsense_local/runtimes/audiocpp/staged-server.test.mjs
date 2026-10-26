import assert from "node:assert/strict"
import test from "node:test"

import { stagedServer } from "./staged-server.mjs"

const nothingUnproven = async () => []

test("with no server staged, staging starts from nothing", async () => {
  const staged = await stagedServer("out", { exists: () => false, probe: nothingUnproven })
  assert.equal(staged.state, "absent")
})

test("keeps a staged server that proves every curated family", async () => {
  const staged = await stagedServer("out", { exists: () => true, probe: nothingUnproven })
  assert.equal(staged.state, "current")
})

test("stages again a server built before a family joined the pins, naming it", async () => {
  const staged = await stagedServer("out", {
    exists: () => true,
    probe: async () => [
      { family: "canary_asr", verdict: "missing", output: "unsupported model family hint: canary_asr" },
    ],
  })
  assert.equal(staged.state, "stale")
  assert.match(staged.reason, /built without canary_asr/)
})

test("says a staged server that would not run did not run, not that it lacks families", async () => {
  const staged = await stagedServer("out", {
    exists: () => true,
    probe: async () => [
      { family: "kokoro_tts", verdict: "unknown", output: "" },
      { family: "canary_asr", verdict: "unknown", output: "" },
    ],
  })
  assert.equal(staged.state, "stale")
  assert.match(staged.reason, /did not run/)
  assert.doesNotMatch(staged.reason, /built without/)
})
