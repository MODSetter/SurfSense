import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"

// electron-updater's update-info.json names the file but not its version. The
// record sits beside it, so emptying the folder for a new download drops it too.
const RECORD = "downloaded-version.json"

export function recordDownloadedVersion(pendingFolder: string, version: string): void {
  try {
    writeFileSync(join(pendingFolder, RECORD), JSON.stringify({ version }))
  } catch {
    // Unrecorded, the download is freed at the next launch and fetched again if needed.
  }
}

/** The recorded version; undefined when nothing was recorded, null when it is unreadable. */
export function readDownloadedVersion(pendingFolder: string): string | null | undefined {
  let text: string
  try {
    text = readFileSync(join(pendingFolder, RECORD), "utf8")
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "ENOENT" ? undefined : null
  }
  try {
    const version = (JSON.parse(text) as { version?: unknown }).version
    return typeof version === "string" ? version : null
  } catch {
    return null
  }
}
