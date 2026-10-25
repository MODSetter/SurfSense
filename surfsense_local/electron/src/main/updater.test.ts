import assert from "node:assert/strict"
import test from "node:test"

import type { UpdateFeed } from "./update-feed/latest-manifest.ts"
import {
  SurfSenseFeedProvider,
  type SurfSenseFeedOptions,
} from "./update-feed/surfsense-feed-provider.ts"
import { attachUpdater, parseUpdatePrefs, type UpdateState } from "./updater.ts"

const FEED: UpdateFeed = {
  base: "https://updates.surfsense.com/api/updates/",
  mirror: false,
  channelFile: "stable.yml",
  headers: { "X-SurfSense-Version": "2.2.3" },
  fetch: (async () => new Response(null, { status: 503 })) as typeof fetch,
}

type Listener = (...args: unknown[]) => void

function fakeAutoUpdater() {
  const listeners = new Map<string, Listener>()
  const calls: string[] = []
  const feeds: SurfSenseFeedOptions[] = []
  return {
    calls,
    feeds,
    emit: (event: string, ...args: unknown[]) => listeners.get(event)?.(...args),
    updater: {
      autoDownload: true,
      autoInstallOnAppQuit: false,
      requestHeaders: null as Record<string, string> | null,
      setFeedURL(options: SurfSenseFeedOptions) {
        feeds.push(options)
      },
      on(event: string, listener: Listener) {
        listeners.set(event, listener)
      },
      checkForUpdates: async (): Promise<unknown> => {
        calls.push("check")
        return { isUpdateAvailable: false }
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
  const updates = attachUpdater(fake.updater, (state) => states.push(state), FEED)

  assert.equal(fake.updater.autoDownload, false)
  await updates.check()
  fake.emit("update-available", { version: "1.0.1" })
  fake.emit("update-downloaded", { version: "1.0.1" })

  assert.deepEqual(fake.calls, ["check", "download"])
  assert.deepEqual(states, [
    { status: "checking" },
    { status: "downloading", version: "1.0.1", percent: null },
    { status: "ready", version: "1.0.1" },
  ])
  assert.deepEqual(updates.state(), { status: "ready", version: "1.0.1" })

  updates.install()
  assert.deepEqual(fake.calls, ["check", "download", "install"])
})

test("a download reports its progress in whole percents, once per step", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state), FEED)

  await updates.check()
  fake.emit("update-available", { version: "1.0.1" })
  for (const percent of [0.4, 12.2, 12.9, 64.5, 100])
    fake.emit("download-progress", { percent, total: 1000 })
  // No size known yet, so no percentage to show.
  fake.emit("download-progress", { percent: 0, total: 0 })

  assert.deepEqual(
    states.slice(1).map((state) => (state.status === "downloading" ? state.percent : state.status)),
    [null, 0, 12, 64, 100, null]
  )
  assert.deepEqual(updates.state(), { status: "downloading", version: "1.0.1", percent: null })
})

test("progress after the download finished leaves it ready", async () => {
  const fake = fakeAutoUpdater()
  const updates = attachUpdater(fake.updater, () => undefined, FEED)

  await updates.check()
  fake.emit("update-available", { version: "1.0.1" })
  fake.emit("update-downloaded", { version: "1.0.1" })
  fake.emit("download-progress", { percent: 100, total: 1000 })

  assert.deepEqual(updates.state(), { status: "ready", version: "1.0.1" })
})

test("checks go through SurfSense's feed provider, with no headers left for downloads", () => {
  const fake = fakeAutoUpdater()
  fake.updater.requestHeaders = { "x-user-staging-id": "0" }

  attachUpdater(fake.updater, () => undefined, FEED)

  // providerFactory.js builds `updateProvider` with these options on each check.
  assert.equal(fake.feeds.length, 1)
  assert.equal(fake.feeds[0]!.provider, "custom")
  assert.equal(fake.feeds[0]!.updateProvider, SurfSenseFeedProvider)
  assert.equal(fake.feeds[0]!.feed, FEED)
  // AppUpdater merges requestHeaders into every installer download.
  assert.equal(fake.updater.requestHeaders, null)
  // Its setter turns on allowDowngrade, so it is never set.
  assert.equal("channel" in fake.updater, false)
})

test("a downloaded update installs on restart or, failing that, on quit", () => {
  const fake = fakeAutoUpdater()

  attachUpdater(fake.updater, () => undefined, FEED)

  // Set on purpose: the docs and the update prompt say quitting installs it.
  assert.equal(fake.updater.autoInstallOnAppQuit, true)
})

test("no update and errors both settle back to a state the UI can show", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state), FEED)

  await updates.check()
  fake.emit("update-not-available")
  fake.emit("error", new Error("net::ERR_INTERNET_DISCONNECTED\nstack"))

  assert.deepEqual(states, [
    { status: "checking" },
    { status: "up-to-date" },
    { status: "error", message: "net::ERR_INTERNET_DISCONNECTED" },
  ])
})

test("a check says whether it read a manifest, so a failed one can be retried", async () => {
  const fake = fakeAutoUpdater()
  const updates = attachUpdater(fake.updater, () => undefined, FEED)

  assert.equal(await updates.check(), true)

  fake.updater.checkForUpdates = async () => {
    throw new Error("updates.surfsense.com (unreachable) and github.com (unreachable) could not be used")
  }
  assert.equal(await updates.check(), false)

  // AppUpdater's answer when it is not active: nothing was read.
  fake.updater.checkForUpdates = async () => null
  assert.equal(await updates.check(), false)
})

test("an inactive updater settles back to idle instead of staying on checking", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state), FEED)
  // AppImageUpdater outside an AppImage, or inside a snap: no event, no manifest.
  fake.updater.checkForUpdates = async () => null

  assert.equal(await updates.check(), false)

  assert.deepEqual(states, [{ status: "checking" }, { status: "idle" }])
  assert.deepEqual(updates.state(), { status: "idle" })
})

test("an inactive check keeps a downloaded update's restart prompt", async () => {
  const fake = fakeAutoUpdater()
  const updates = attachUpdater(fake.updater, () => undefined, FEED)
  await updates.check()
  fake.emit("update-available", { version: "1.0.1" })
  fake.emit("update-downloaded", { version: "1.0.1" })
  fake.updater.checkForUpdates = async () => null

  assert.equal(await updates.check(), false)

  assert.deepEqual(updates.state(), { status: "ready", version: "1.0.1" })
})

test("a failed check stays on the error it emitted", async () => {
  const fake = fakeAutoUpdater()
  const states: UpdateState[] = []
  const updates = attachUpdater(fake.updater, (state) => states.push(state), FEED)
  // AppUpdater emits "error" and then rethrows.
  fake.updater.checkForUpdates = async () => {
    fake.emit("error", new Error("github.com (unreachable) could not be used"))
    throw new Error("github.com (unreachable) could not be used")
  }

  assert.equal(await updates.check(), false)

  assert.deepEqual(states, [
    { status: "checking" },
    { status: "error", message: "github.com (unreachable) could not be used" },
  ])
})

test("install is a no-op until something is downloaded", () => {
  const fake = fakeAutoUpdater()
  const updates = attachUpdater(fake.updater, () => undefined, FEED)

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
  assert.deepEqual(
    parseUpdatePrefs({ automatic: true, lastAutomaticDay: "2026-10-21" }),
    { automatic: true, lastAutomaticDay: "2026-10-21" }
  )
  assert.deepEqual(parseUpdatePrefs({ lastAutomaticDay: "yesterday" }), {
    automatic: false,
  })
})
