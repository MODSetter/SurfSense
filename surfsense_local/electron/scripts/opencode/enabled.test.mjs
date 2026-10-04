import assert from "node:assert/strict"
import test from "node:test"

import { opencodeEnabled } from "./enabled.mjs"

test("opencode is off unless something turns it on", () => {
  assert.equal(opencodeEnabled({}), false)
})

test("SURFSENSE_LOCAL_OPENCODE_ENABLED turns it on with 1 and off with 0", () => {
  assert.equal(opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: "1" }), true)
  assert.equal(opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: "0" }), false)
})
