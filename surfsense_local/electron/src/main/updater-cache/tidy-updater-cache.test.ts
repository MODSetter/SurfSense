import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, readdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import type { Updates } from "../updater.ts"
import { tidyUpdaterCache } from "./tidy-updater-cache.ts"

type Listener = (info: { version: string }) => void

function fakeUpdater() {
  const listeners = new Map<string, Listener[]>()
  return {
    emit: (event: string, version = "") =>
      listeners.get(event)?.forEach((listener) => listener({ version })),
    on(event: string, listener: Listener) {
      listeners.set(event, [...(listeners.get(event) ?? []), listener])
    },
  }
}

/** electron-updater's cache: the differential base, and pending/ once it downloads. */
function updaterCache() {
  const root = mkdtempSync(join(tmpdir(), "updater-cache-"))
  writeFileSync(join(root, "installer.exe"), "installed version")
  writeFileSync(join(root, "current.blockmap"), "blockmap")
  return { root, pending: join(root, "pending") }
}

function download(pending: string) {
  mkdirSync(pending, { recursive: true })
  writeFileSync(join(pending, "SurfSense-Setup.exe"), "downloaded version")
  writeFileSync(join(pending, "update-info.json"), '{"fileName":"SurfSense-Setup.exe"}')
}

/** The app's Updates, whose check notes whether pending/ still existed when it ran. */
function launch(
  pending: string | null,
  installedVersion: string,
  platform: NodeJS.Platform = "linux",
  updater = fakeUpdater()
) {
  const seen: { pendingAtCheck?: boolean; installs: number } = { installs: 0 }
  const inner: Updates = {
    check: async () => {
      seen.pendingAtCheck = pending !== null && existsSync(pending)
    },
    install: () => {
      seen.installs++
    },
    state: () => ({ status: "idle" }),
  }
  const updates = tidyUpdaterCache(updater, inner, {
    pendingFolder: pending,
    installedVersion,
    platform,
  })
  return { updater, updates, seen }
}

/** One launch at `installed` that downloads `downloaded`. */
async function downloadOn(pending: string, installed: string, downloaded: string) {
  const { updater, updates } = launch(pending, installed)
  await updates.check()
  download(pending)
  updater.emit("update-available", downloaded)
  updater.emit("update-downloaded", downloaded)
}

test("an update already installed is freed before the first check, and the differential base stays", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4")

  const { updates, seen } = launch(pending, "2.2.4")
  await updates.check()

  assert.equal(seen.pendingAtCheck, false)
  assert.deepEqual(readdirSync(root).sort(), ["current.blockmap", "installer.exe"])
})

test("an update still waiting to be installed is kept", async () => {
  const { pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4")

  const { updates, seen } = launch(pending, "2.2.3")
  await updates.check()

  assert.equal(seen.pendingAtCheck, true)
  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))
  assert.ok(existsSync(join(pending, "update-info.json")))
})

test("versions compare by number, not by text", async () => {
  const { pending } = updaterCache()
  await downloadOn(pending, "2.9.9", "2.10.0")

  await launch(pending, "2.9.9").updates.check()

  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))
})

test("an update older than the installed app is freed", async () => {
  const { pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4")

  await launch(pending, "2.3.0").updates.check()

  assert.equal(existsSync(pending), false)
})

test("a download no launch recorded is freed: an older app made it", async () => {
  const { pending } = updaterCache()
  download(pending)

  await launch(pending, "2.2.4").updates.check()

  assert.equal(existsSync(pending), false)
})

test("a record that makes no sense keeps the download, as before", async () => {
  const { pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "not-a-version")
  await launch(pending, "2.2.4").updates.check()
  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))

  writeFileSync(join(pending, "downloaded-version.json"), '{"version":')
  await launch(pending, "2.2.4").updates.check()
  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))
})

test("an installed prerelease never frees a download it cannot order", async () => {
  const { pending } = updaterCache()
  await downloadOn(pending, "2.2.4-test", "2.2.4")

  await launch(pending, "2.2.4-test").updates.check()

  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))
})

test("a kept download is freed once the feed offers nothing newer", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4")
  const { updater, updates, seen } = launch(pending, "2.2.3")
  await updates.check()
  assert.equal(seen.pendingAtCheck, true)

  // 2.2.4 was pulled: the feed's newest is the installed 2.2.3.
  updater.emit("update-not-available", "2.2.3")
  await updates.check()

  assert.equal(seen.pendingAtCheck, false)
  assert.deepEqual(readdirSync(root).sort(), ["current.blockmap", "installer.exe"])
})

test("a download offered this session stays, whatever a later check says", async () => {
  const { pending } = updaterCache()
  const { updater, updates } = launch(pending, "2.2.3")
  await updates.check()
  updater.emit("update-available", "2.2.4")
  download(pending)
  updater.emit("update-downloaded", "2.2.4")

  // Installing at quit still uses it.
  updater.emit("update-not-available", "2.2.3")
  await updates.check()

  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))
})

test("on Windows each check drops the blockmap, never installer.exe or a waiting download", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4")
  const { updates } = launch(pending, "2.2.3", "win32")

  await updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["installer.exe", "pending"])
  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))

  // A download in this session leaves its own blockmap; the next check drops it too.
  writeFileSync(join(root, "current.blockmap"), "2.2.4's blockmap")
  await updates.check()
  assert.equal(existsSync(join(root, "current.blockmap")), false)
})

test("on macOS update.zip and its blockmap are one download, so both stay", async () => {
  const { root, pending } = updaterCache()
  writeFileSync(join(root, "update.zip"), "last downloaded version")

  await launch(pending, "2.2.4", "darwin").updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["current.blockmap", "installer.exe", "update.zip"])
})

test("checks still run without a cache, or before the first download", async () => {
  const none = launch(null, "2.2.4", "win32")
  await none.updates.check()
  assert.equal(none.seen.pendingAtCheck, false)

  const root = mkdtempSync(join(tmpdir(), "updater-cache-"))
  const empty = launch(join(root, "pending"), "2.2.4", "win32")
  await empty.updates.check()
  assert.equal(empty.seen.pendingAtCheck, false)
  assert.deepEqual(readdirSync(root), [])
})

test("install and state pass straight through", () => {
  const { updates, seen } = launch(null, "2.2.4")
  updates.install()
  assert.equal(seen.installs, 1)
  assert.deepEqual(updates.state(), { status: "idle" })
})
