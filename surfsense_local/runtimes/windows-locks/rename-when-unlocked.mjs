// A rename that waits out Windows holding a file open inside the folder being renamed.
import { renameSync } from "node:fs"
import { setTimeout as sleep } from "node:timers/promises"

// Only Windows answers this way for a file another process holds open; elsewhere they are real permission errors.
const LOCKED = new Set(["EPERM", "EACCES", "EBUSY"])

/** Rename `from` to `to`, retrying while another process holds a file in it, such as a Windows
 * service reading a binary we just ran. 60 s by default: the window graceful-fs waits for the same lock. */
export async function renameWhenUnlocked(from, to, { rename = renameSync, timeoutMs = 60_000, platform = process.platform } = {}) {
  const start = Date.now()
  for (let attempt = 1; ; attempt++) {
    try {
      return rename(from, to)
    } catch (error) {
      if (platform !== "win32" || !LOCKED.has(error.code) || Date.now() - start >= timeoutMs) throw error
      if (attempt === 1) console.warn(`rename of ${from} blocked (${error.code}), retrying for up to ${timeoutMs / 1000} s`)
      await sleep(Math.min(10 * attempt, 100))
    }
  }
}

