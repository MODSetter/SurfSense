import assert from "node:assert/strict"
import test from "node:test"

import { attachUpdater, parseUpdatePrefs, type UpdateState } from "./updater.ts"

type Listener = (...args: unknown[]) => void

function fakeAutoUpdater() {
  const listeners = new Map<string, Listener>()
  const calls: string[] = []
  return {
    calls,
    emit: (event: string, ...args: unknown[]) => listeners.get(event)?.(...args),
    updater: {
      autoDownload: true,
      allowPrerelease: false,
      on(event: string, listener: Listener) {
        listeners.set(event, listener)
      },
      async checkForUpdates() {
        calls.push("check")
        return null
      },
      async downloadUpdate() {
        calls.push("download")
        return []
      },
      quitAndInstall() {
        calls.push("install")
      },
    },
  }
}

test("a found update is downloaded and offered, never installed on its own", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state))

  assert.equal(fake.updater.autoDownload, false)
  // Walks the releases feed rather than /releases/latest; see updater.ts.
  assert.equal(fake.updater.allowPrerelease, true)
  await updates.check()
  fake.emit("update-available", { version: "1.0.1" })
  fake.emit("update-downloaded", { version: "1.0.1" })

  assert.deepEqual(fake.calls, ["check", "download"])
  assert.deepEqual(states, [
    { status: "checking" },
    { status: "downloading", version: "1.0.1" },
    { status: "ready", version: "1.0.1" },
  ])
  assert.deepEqual(updates.state(), { status: "ready", version: "1.0.1" })

  updates.install()
  assert.deepEqual(fake.calls, ["check", "download", "install"])
})

test("no update and errors both settle back to a state the UI can show", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state))

  await updates.check()
  fake.emit("update-not-available")
  fake.emit("error", new Error("net::ERR_INTERNET_DISCONNECTED\nstack"))

  assert.deepEqual(states, [
    { status: "checking" },
    { status: "up-to-date" },
    { status: "error", message: "net::ERR_INTERNET_DISCONNECTED" },
  ])
})

test("install is a no-op until something is downloaded", () => {
  const fake = fakeAutoUpdater()
  const updates = attachUpdater(fake.updater, () => undefined)

  updates.install()

  assert.deepEqual(fake.calls, [])
})

test("update prefs default to off and ignore junk", () => {
  assert.deepEqual(parseUpdatePrefs(undefined), { automatic: false })
  assert.deepEqual(parseUpdatePrefs({ automatic: "yes" }), { automatic: false })
  assert.deepEqual(parseUpdatePrefs({ automatic: true }), { automatic: true })
  assert.deepEqual(
    parseUpdatePrefs({ automatic: true, lastCheckedAt: "2026-09-14T10:00:00Z" }),
    { automatic: true, lastCheckedAt: "2026-09-14T10:00:00Z" }
  )
  assert.deepEqual(parseUpdatePrefs({ lastCheckedAt: 5 }), { automatic: false })
})
