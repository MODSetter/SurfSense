import assert from "node:assert/strict"
import test from "node:test"

import { opencodeEnabled } from "./enabled.mjs"

test("opencode is on unless something turns it off, so every installer carries the agent", () => {
  assert.equal(opencodeEnabled({}), true)
})

test("SURFSENSE_LOCAL_OPENCODE_ENABLED turns it on with 1 and off with 0", () => {
  assert.equal(opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: "1" }), true)
  assert.equal(opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: "0" }), false)
})

test("an empty switch, as an unset CI variable gives, keeps the default", () => {
  assert.equal(opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: "" }), true)
})

test("any other value is refused, so a build never drops the agent on a misread switch", () => {
  for (const value of ["true", "yes", "false"]) {
    assert.throws(
      () => opencodeEnabled({ SURFSENSE_LOCAL_OPENCODE_ENABLED: value }),
      new RegExp(`is "${value}"; set it to 1 or 0`)
    )
  }
})
