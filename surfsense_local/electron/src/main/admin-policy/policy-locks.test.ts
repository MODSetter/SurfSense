import assert from "node:assert/strict"
import test from "node:test"

import { updatesLockReason } from "./policy-locks.ts"
import { readPolicy } from "./read-policy.ts"

function policy(contents: object | null) {
  return readPolicy({
    platform: "linux",
    env: {},
    readFile: () => {
      if (contents === null) throw Object.assign(new Error("ENOENT"), { code: "ENOENT" })
      return JSON.stringify(contents)
    },
  })
}

test("a package manager that owns updates locks them for the channel", () => {
  assert.equal(updatesLockReason(policy(null), "snap"), "channel")
  assert.equal(updatesLockReason(policy({ updates: "user" }), "apt"), "channel")
})

test("the policy names the lock when both apply", () => {
  assert.equal(updatesLockReason(policy({ updates: "off" }), "snap"), "policy")
  assert.equal(updatesLockReason(policy({ updates: "off" }), null), "policy")
})

test("with neither, updates stay the user's", () => {
  assert.equal(updatesLockReason(policy(null), null), null)
})
