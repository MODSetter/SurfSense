import assert from "node:assert/strict"
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
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

/** A differential attempt saves the new version's blockmap in pending/ first; a whole download saves none. */
function download(pending: string, blockmap?: string) {
  mkdirSync(pending, { recursive: true })
  writeFileSync(join(pending, "SurfSense-Setup.exe"), "downloaded version")
  writeFileSync(join(pending, "update-info.json"), '{"fileName":"SurfSense-Setup.exe"}')
  if (blockmap !== undefined) writeFileSync(join(pending, "current.blockmap"), blockmap)
}

/** electron-updater 6.8.9's order: update-downloaded, then pending/'s blockmap copied beside installer.exe. */
function finish(updater: ReturnType<typeof fakeUpdater>, pending: string, version: string) {
  updater.emit("update-downloaded", version)
  const saved = join(pending, "current.blockmap")
  if (existsSync(saved)) copyFileSync(saved, join(dirname(pending), "current.blockmap"))
}

const blockmapIn = (root: string) => readFileSync(join(root, "current.blockmap"), "utf8")

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
      return true
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
async function downloadOn(
  pending: string,
  installed: string,
  downloaded: string,
  platform: NodeJS.Platform = "linux"
) {
  const { updater, updates } = launch(pending, installed, platform)
  await updates.check()
  updater.emit("update-available", downloaded)
  download(pending, `${downloaded}'s blockmap`)
  finish(updater, pending, downloaded)
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

test("on Windows a blockmap that is not the installed version's is dropped, never installer.exe or a waiting download", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4", "win32")
  const { updater, updates } = launch(pending, "2.2.3", "win32")

  await updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["installer.exe", "pending"])
  assert.ok(existsSync(join(pending, "SurfSense-Setup.exe")))

  // Offered again, the waiting download leaves its blockmap again; the next check drops it too.
  updater.emit("update-available", "2.2.4")
  finish(updater, pending, "2.2.4")
  assert.equal(blockmapIn(root), "2.2.4's blockmap")
  await updates.check()
  assert.deepEqual(readdirSync(root).sort(), ["installer.exe", "pending"])
})

test("on Windows an update installed through the updater keeps its own blockmap", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4", "win32")
  // Installing at quit: the installer copies itself over installer.exe.
  writeFileSync(join(root, "installer.exe"), "2.2.4")

  const { updates } = launch(pending, "2.2.4", "win32")
  await updates.check()
  await updates.check()

  // So the next update never needs 2.2.4's release to still be published.
  assert.equal(blockmapIn(root), "2.2.4's blockmap")
  assert.equal(existsSync(pending), false)
})

test("on Windows a version installed by hand drops the downloaded version's blockmap", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.3", "2.2.4", "win32")
  writeFileSync(join(root, "installer.exe"), "2.2.5")

  await launch(pending, "2.2.5", "win32").updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["installer.exe"])
})

test("on Windows a whole download leaves the old blockmap, which is then dropped", async () => {
  const { root, pending } = updaterCache()
  await downloadOn(pending, "2.2.2", "2.2.3", "win32")
  writeFileSync(join(root, "installer.exe"), "2.2.3")
  const { updater, updates } = launch(pending, "2.2.3", "win32")
  await updates.check()
  assert.equal(blockmapIn(root), "2.2.3's blockmap")

  // 2.2.4's blockmap could not be fetched, so it downloaded whole and saved none.
  updater.emit("update-available", "2.2.4")
  download(pending)
  finish(updater, pending, "2.2.4")
  writeFileSync(join(root, "installer.exe"), "2.2.4")
  await launch(pending, "2.2.4", "win32").updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["installer.exe"])
})

test("on Windows a second download in one launch never takes the first one's blockmap as its own", async () => {
  const { root, pending } = updaterCache()
  const { updater, updates } = launch(pending, "2.2.3", "win32")
  await updates.check()
  updater.emit("update-available", "2.2.4")
  download(pending, "2.2.4's blockmap")
  finish(updater, pending, "2.2.4")

  // Installing failed to start, and Check now offers 2.2.5. electron-updater
  // reuses pending/ as it is, and 2.2.5's blockmap cannot be fetched.
  await updates.check()
  updater.emit("update-available", "2.2.5")
  writeFileSync(join(pending, "SurfSense-Setup.exe"), "2.2.5")
  finish(updater, pending, "2.2.5")
  writeFileSync(join(root, "installer.exe"), "2.2.5")
  await launch(pending, "2.2.5", "win32").updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["installer.exe"])
})

test("on macOS update.zip and its blockmap are left as they are, and nothing joins them", async () => {
  const { root, pending } = updaterCache()
  writeFileSync(join(root, "update.zip"), "last downloaded version")
  await downloadOn(pending, "2.2.3", "2.2.4", "darwin")

  await launch(pending, "2.2.5", "darwin").updates.check()

  assert.deepEqual(readdirSync(root).sort(), ["current.blockmap", "installer.exe", "update.zip"])
  assert.equal(blockmapIn(root), "2.2.4's blockmap")
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
