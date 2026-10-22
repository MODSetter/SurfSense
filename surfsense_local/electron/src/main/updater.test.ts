import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

import {
  attachUpdater,
  NO_INSTALL_ID,
  parseUpdatePrefs,
  type UpdateState,
} from "./updater.ts"

type Listener = (...args: unknown[]) => void

// computeFinalHeaders is private in electron-updater's types.
const loadCommonJs = createRequire(import.meta.url)

function fakeAutoUpdater() {
  const listeners = new Map<string, Listener>()
  const calls: string[] = []
  return {
    calls,
    emit: (event: string, ...args: unknown[]) => listeners.get(event)?.(...args),
    updater: {
      autoDownload: true,
      autoInstallOnAppQuit: false,
      allowPrerelease: false,
      requestHeaders: null as Record<string, string> | null,
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

test("a found update is downloaded and offered, and waits for a restart or a quit", async () => {
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

test("update requests carry a constant in place of the persistent install ID", () => {
  const fake = fakeAutoUpdater()
  fake.updater.requestHeaders = { accept: "*/*" }

  attachUpdater(fake.updater, () => undefined)

  // electron-updater sends its own x-user-staging-id, read from
  // userData/.updaterId, on the feed and manifest requests.
  assert.equal(NO_INSTALL_ID, "0")
  assert.deepEqual(fake.updater.requestHeaders, {
    accept: "*/*",
    "x-user-staging-id": "0",
  })
})

test("the installed electron-updater lets the constant win over the install ID", () => {
  const fake = fakeAutoUpdater()
  attachUpdater(fake.updater, () => undefined)

  // The merge electron-updater runs before the feed and manifest requests, so
  // a version that merged the other way fails here rather than in the field.
  const { AppUpdater } = loadCommonJs("electron-updater/out/AppUpdater")
  const sent = AppUpdater.prototype.computeFinalHeaders.call(
    { requestHeaders: fake.updater.requestHeaders },
    { "x-user-staging-id": "6f1c2c1e-7b8a-4f43-9a51-3c7e0f2d9b11" }
  )

  assert.equal(sent["x-user-staging-id"], NO_INSTALL_ID)
})

test("a downloaded update installs on restart or, failing that, on quit", () => {
  const fake = fakeAutoUpdater()

  attachUpdater(fake.updater, () => undefined)

  // Set on purpose: the docs and the update prompt say quitting installs it.
  assert.equal(fake.updater.autoInstallOnAppQuit, true)
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
