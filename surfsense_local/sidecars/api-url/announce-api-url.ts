// Where the API answers, for tools outside the app: `surfsense-plugins invoke`
// reads it, so a plugin author never looks up a port that changes every launch.
// It discloses nothing: loopback already answers a port scan.
import { rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"

const FILE = "api-url"

/** Written once the API answers, in the app's own data folder. */
export function announceApiUrl(dataDir: string, apiUrl: string): void {
  writeFileSync(join(dataDir, FILE), apiUrl)
}

/** Removed on quit, so no tool finds an app that is gone. */
export function withdrawApiUrl(dataDir: string): void {
  rmSync(join(dataDir, FILE), { force: true })
}
