import assert from "node:assert/strict"
import test from "node:test"

import { updatesLocked, usageLockReason } from "./policy-locks.ts"
import { policyPath, readPolicy } from "./read-policy.ts"

function missing(): string {
  throw Object.assign(new Error("ENOENT"), { code: "ENOENT" })
}

function policy(contents: unknown, env: Record<string, string> = {}) {
  return readPolicy({
    platform: "linux",
    env,
    readFile: (path) => {
      assert.equal(path, "/etc/surfsense/policy.json")
      return typeof contents === "string" ? contents : JSON.stringify(contents)
    },
  })
}

test("reads the policy from each system's machine-wide place", () => {
  assert.equal(
    policyPath("win32", { ProgramData: "D:\\ProgramData" }),
    "D:\\ProgramData\\SurfSense\\policy.json"
  )
  assert.equal(policyPath("win32", {}), "C:\\ProgramData\\SurfSense\\policy.json")
  assert.equal(
    policyPath("darwin", {}),
    "/Library/Application Support/SurfSense/policy.json"
  )
  assert.equal(policyPath("linux", {}), "/etc/surfsense/policy.json")
})

test("no policy file leaves both choices to the user", () => {
  const open = readPolicy({ platform: "linux", env: {}, readFile: missing })

  assert.equal(updatesLocked(open), false)
  assert.equal(usageLockReason(open), null)
  assert.equal(open.updateFeed, null)
  assert.equal(open.problem, null)
})

test("DO_NOT_TRACK and SURFSENSE_NO_TELEMETRY lock usage statistics off, not updates", () => {
  for (const env of [{ DO_NOT_TRACK: "1" }, { SURFSENSE_NO_TELEMETRY: "1" }, { DO_NOT_TRACK: "true" }]) {
    const forced = readPolicy({ platform: "linux", env, readFile: missing })
    assert.equal(usageLockReason(forced), "do_not_track")
    assert.equal(updatesLocked(forced), false)
  }
  const unset = readPolicy({ platform: "linux", env: { DO_NOT_TRACK: "0" }, readFile: missing })
  assert.equal(usageLockReason(unset), null)
})

test("the admin's off locks a setting; user leaves it to the user", () => {
  const off = policy({ updates: "off", usageStatistics: "off" })
  assert.equal(updatesLocked(off), true)
  assert.equal(usageLockReason(off), "policy")

  const user = policy({ updates: "user", usageStatistics: "user" }, { DO_NOT_TRACK: "1" })
  assert.equal(updatesLocked(user), false)
  // The policy names the stronger reason when both apply.
  assert.equal(usageLockReason(policy({ usageStatistics: "off" }, { DO_NOT_TRACK: "1" })), "policy")
  assert.equal(usageLockReason(user), "do_not_track")
})

test("an https mirror replaces the feed", () => {
  const mirrored = policy({ updateFeed: "https://updates.corp.example/surfsense/" })

  assert.equal(mirrored.updateFeed, "https://updates.corp.example/surfsense/")
  assert.equal(updatesLocked(mirrored), false)
})

test("anything unreadable turns the settings off rather than on", () => {
  for (const contents of ["{not json", "[]", "null"]) {
    const broken = policy(contents)
    assert.equal(updatesLocked(broken), true, contents)
    assert.equal(usageLockReason(broken), "policy", contents)
    assert.ok(broken.problem, contents)
  }
  const typo = policy({ updates: "on", usageStatistics: "yes" })
  assert.equal(updatesLocked(typo), true)
  assert.equal(usageLockReason(typo), "policy")

  // A mirror that is not https is never asked, and nothing else is either.
  const plainHttp = policy({ updateFeed: "http://updates.corp.example/" })
  assert.equal(plainHttp.updateFeed, null)
  assert.equal(updatesLocked(plainHttp), true)
  assert.equal(usageLockReason(plainHttp), null)
})
