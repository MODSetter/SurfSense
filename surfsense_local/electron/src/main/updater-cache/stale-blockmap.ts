import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { rm } from "node:fs/promises"
import { dirname, join } from "node:path"

import { readDownloadedVersion } from "./downloaded-version.ts"

/*
 * On Windows electron-updater patches installer.exe, which every install
 * overwrites, using current.blockmap, which every download replaces. A mismatch
 * fails the sha512 and downloads in full; a missing one is fetched from the
 * installed version's release, which 404s once that release is pulled. macOS
 * normally keeps update.zip and its blockmap from one download (Known gaps in
 * updates.md); Linux has neither.
 */
const BLOCKMAP = "current.blockmap"
// electron-updater does not record which version current.blockmap describes.
const RECORD = "current-blockmap-version.json"

/**
 * On update-available. A second download in one launch reuses pending/ without
 * emptying it, and saves its own blockmap there only once that is fetched.
 */
export function dropEarlierDownloadsBlockmap(
  pendingFolder: string,
  offered: string,
  platform: NodeJS.Platform
): void {
  // A download offered again is reused whole, its blockmap included.
  if (platform !== "win32" || readDownloadedVersion(pendingFolder) === offered) return
  try {
    rmSync(join(pendingFolder, BLOCKMAP), { force: true })
  } catch {
    // Left in place, it can be taken for this download's: the next update then downloads whole.
  }
}

/**
 * On update-downloaded, which electron-updater 6.8.9 emits just before copying
 * pending/'s blockmap out. A whole download saves none there, so the older one
 * beside installer.exe stays, unrecorded.
 */
export function recordBlockmapVersion(
  pendingFolder: string,
  version: string,
  platform: NodeJS.Platform
): void {
  if (platform !== "win32") return
  const record = join(dirname(pendingFolder), RECORD)
  try {
    rmSync(record, { force: true })
    if (existsSync(join(pendingFolder, BLOCKMAP))) {
      writeFileSync(record, JSON.stringify({ version }))
    }
  } catch {
    // Unrecorded, the blockmap is dropped at the next check.
  }
}

/** Before each check: keeps current.blockmap only when it is the installed version's. */
export async function dropStaleBlockmap(
  pendingFolder: string,
  installedVersion: string,
  platform: NodeJS.Platform
): Promise<void> {
  if (platform !== "win32") return
  const root = dirname(pendingFolder)
  if (recordedVersion(root) === installedVersion) return
  await Promise.all(
    [BLOCKMAP, RECORD].map((name) =>
      rm(join(root, name), { force: true }).catch(() => undefined)
    )
  )
}

function recordedVersion(root: string): string | undefined {
  try {
    const { version } = JSON.parse(readFileSync(join(root, RECORD), "utf8")) as {
      version?: unknown
    }
    return typeof version === "string" ? version : undefined
  } catch {
    return undefined
  }
}
