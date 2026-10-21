import { readFileSync, renameSync, writeFileSync } from "node:fs"
import type { OutgoingHttpHeaders } from "node:http"

// The subset of electron-updater's AppUpdater this module touches, so the
// state machine runs under node --test without Electron.
export type AutoUpdaterLike = {
  autoDownload: boolean
  autoInstallOnAppQuit: boolean
  allowPrerelease: boolean
  requestHeaders: OutgoingHttpHeaders | null
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
export type UpdatePrefs = { automatic: boolean; lastCheckedAt?: string }

export type Updates = {
  check(): Promise<void>
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

export function parseUpdatePrefs(value: unknown): UpdatePrefs {
  const record =
    typeof value === "object" && value !== null
      ? (value as Record<string, unknown>)
      : {}
  const automatic = record.automatic === true
  return typeof record.lastCheckedAt === "string"
    ? { automatic, lastCheckedAt: record.lastCheckedAt }
    : { automatic }
}

// What update requests send in place of the install ID.
export const NO_INSTALL_ID = "0"

export function attachUpdater(
  updater: AutoUpdaterLike,
  onState: (state: UpdateState) => void
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
  // electron-updater sends its persistent install ID from userData/.updaterId
  // as this header; ours are merged over it, so no ID leaves. Staged rollouts
  // still read the local file.
  updater.requestHeaders = {
    ...updater.requestHeaders,
    "x-user-staging-id": NO_INSTALL_ID,
  }
  // Takes the newest entry of the releases feed rather than /releases/latest.
  // That pointer names a 2.x release again, so this is no longer required;
  // dropping it changes behaviour for shipped clients, so it ships on its own.
  updater.allowPrerelease = true
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
      // Failures surface through the "error" event above.
      await updater.checkForUpdates().catch(() => undefined)
    },
    install() {
      if (current.status === "ready") updater.quitAndInstall()
    },
    state: () => current,
  }
}
