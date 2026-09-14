import { readFileSync, renameSync, writeFileSync } from "node:fs"

// The subset of electron-updater's AppUpdater this module touches, so the
// state machine runs under node --test without Electron.
export type AutoUpdaterLike = {
  autoDownload: boolean
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
  // check they enabled or clicked. Installing always waits for them.
  updater.autoDownload = false
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
