import assert from "node:assert/strict"
import test from "node:test"

import { renameWhenUnlocked } from "./rename-when-unlocked.mjs"

/** A stand-in for renameSync that fails with each code in turn, then succeeds. */
function renameFailingWith(...codes) {
  return () => {
    const code = codes.shift()
    if (code) throw Object.assign(new Error(`rename failed: ${code}`), { code })
  }
}

test("a rename that fails for another reason is rethrown without a retry", async () => {
  await assert.rejects(renameWhenUnlocked("stage", "out", { rename: renameFailingWith("ENOENT"), platform: "win32" }), {
    code: "ENOENT",
  })
})

test("a rename Windows refuses twice goes through on the third try", async () => {
  await assert.doesNotReject(
    renameWhenUnlocked("stage", "out", { rename: renameFailingWith("EPERM", "EPERM"), platform: "win32" }),
  )
})

test("a rename locked for longer than the time limit gives up and rethrows EPERM", async () => {
  const lockedFor24Tries = renameFailingWith(...Array(24).fill("EPERM"))
  await assert.rejects(renameWhenUnlocked("stage", "out", { rename: lockedFor24Tries, timeoutMs: 50, platform: "win32" }), {
    code: "EPERM",
  })
})

test("off Windows, a refused rename is rethrown without a retry", async () => {
  await assert.rejects(
    renameWhenUnlocked("stage", "out", { rename: renameFailingWith("EPERM"), platform: "linux" }),
    { code: "EPERM" },
  )
})
