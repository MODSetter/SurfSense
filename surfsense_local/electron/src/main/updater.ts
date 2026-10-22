import { readFileSync, renameSync, writeFileSync } from "node:fs"
import type { OutgoingHttpHeaders } from "node:http"

import type { UpdateFeed } from "./update-feed/latest-manifest.ts"
import {
  surfSenseFeedOptions,
  type SurfSenseFeedOptions,
} from "./update-feed/surfsense-feed-provider.ts"

// The subset of electron-updater's AppUpdater this module touches, so the
// state machine runs under node --test without Electron.
export type AutoUpdaterLike = {
  autoDownload: boolean
  autoInstallOnAppQuit: boolean
  requestHeaders: OutgoingHttpHeaders | null
  setFeedURL(options: SurfSenseFeedOptions): void
  on(event: string, listener: (...args: any[]) => void): unknown
  checkForUpdates(): Promise<unknown>
  downloadUpdate(): Promise<unknown>
  quitAndInstall(): void
}

export type UpdateState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "up-to-date" }
  | { status: "downloading"; version: string }
  | { status: "ready"; version: string }
  | { status: "error"; message: string }

// lastCheckedAt: the "last call" shown in Settings > Network.
// lastAutomaticDay: the UTC day (YYYY-MM-DD) of the last automatic check that
// read a manifest.
export type UpdatePrefs = {
  automatic: boolean
  lastCheckedAt?: string
  lastAutomaticDay?: string
}

export type Updates = {
  /** True once a manifest was read, from either host; failures also reach the "error" state. */
  check(): Promise<boolean>
  install(): void
  state(): UpdateState
}

export function readUpdatePrefs(path: string): UpdatePrefs {
  try {
    return parseUpdatePrefs(JSON.parse(readFileSync(path, "utf8")))
  } catch {
    return { automatic: false }
  }
}

export function writeUpdatePrefs(path: string, prefs: UpdatePrefs): void {
  writeFileSync(`${path}.tmp`, JSON.stringify(prefs))
  renameSync(`${path}.tmp`, path)
}

const UTC_DAY = /^\d{4}-\d{2}-\d{2}$/

export function parseUpdatePrefs(value: unknown): UpdatePrefs {
  const record =
    typeof value === "object" && value !== null
      ? (value as Record<string, unknown>)
      : {}
  return {
    automatic: record.automatic === true,
    ...(typeof record.lastCheckedAt === "string"
      ? { lastCheckedAt: record.lastCheckedAt }
      : {}),
    ...(typeof record.lastAutomaticDay === "string" &&
    UTC_DAY.test(record.lastAutomaticDay)
      ? { lastAutomaticDay: record.lastAutomaticDay }
      : {}),
  }
}

export function attachUpdater(
  updater: AutoUpdaterLike,
  onState: (state: UpdateState) => void,
  feed: UpdateFeed
): Updates {
  let current: UpdateState = { status: "idle" }
  const set = (state: UpdateState) => {
    current = state
    onState(state)
  }

  // Downloading is still the user's call in spirit: it only starts after a
  // check they enabled or clicked.
  updater.autoDownload = false
  // A downloaded update installs on Restart, or else the next time the user
  // quits; the copy and docs say so.
  updater.autoInstallOnAppQuit = true
  // Merged into every download's headers (AppUpdater.computeRequestHeaders), so
  // nothing of ours rides along to GitHub.
  updater.requestHeaders = null
  // The manifest from updates.surfsense.com, falling back to GitHub; never
  // `updater.channel`, whose setter turns on allowDowngrade.
  updater.setFeedURL(surfSenseFeedOptions(feed))
  updater.on("update-available", (info: { version: string }) => {
    set({ status: "downloading", version: info.version })
    updater.downloadUpdate().catch(() => undefined)
  })
  updater.on("update-downloaded", (info: { version: string }) => {
    set({ status: "ready", version: info.version })
  })
  updater.on("update-not-available", () => set({ status: "up-to-date" }))
  updater.on("error", (error: Error) => {
    set({ status: "error", message: error.message.split("\n")[0] ?? "" })
  })

  return {
    async check() {
      set({ status: "checking" })
      // Failures surface through the "error" event above. AppUpdater answers
      // null only when it is inactive, so it read nothing.
      const result = await updater.checkForUpdates().catch(() => null)
      return result !== null
    },
    install() {
      if (current.status === "ready") updater.quitAndInstall()
    },
    state: () => current,
  }
}
