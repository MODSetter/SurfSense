import { rm } from "node:fs/promises"

import type { Updates } from "../updater.ts"
import { readDownloadedVersion, recordDownloadedVersion } from "./downloaded-version.ts"
import {
  dropEarlierDownloadsBlockmap,
  dropStaleBlockmap,
  recordBlockmapVersion,
} from "./stale-blockmap.ts"

type UpdaterEvents = {
  on(
    event: "update-available" | "update-not-available" | "update-downloaded",
    listener: (info: { version: string }) => void
  ): unknown
}

export type UpdaterCache = {
  pendingFolder: string | null
  installedVersion: string
  platform?: NodeJS.Platform
}

/**
 * Free electron-updater's downloaded update once it can no longer be installed:
 * it empties pending/ only when a later launch downloads another version, so a
 * 1.2 GB installer otherwise outlives every update. The differential base beside pending/
 * (installer.exe, update.zip) is left alone.
 *
 * Returns `updates` with each check held until the cache is tidy, so a download
 * never lands in a folder being emptied.
 */
export function tidyUpdaterCache(
  updater: UpdaterEvents,
  updates: Updates,
  { pendingFolder, installedVersion, platform = process.platform }: UpdaterCache
): Updates {
  if (pendingFolder === null) return updates
  let tidying = freeIfInstalled(pendingFolder, installedVersion)
  const queue = (step: () => Promise<void>) => (tidying = tidying.then(step))

  let offered = false
  // Synchronous: electron-updater writes a new blockmap only after fetching it.
  updater.on("update-available", (info) => {
    offered = true
    dropEarlierDownloadsBlockmap(pendingFolder, info.version, platform)
  })
  // Synchronous: electron-updater copies pending/'s blockmap out right after emitting.
  updater.on("update-downloaded", (info) => {
    recordDownloadedVersion(pendingFolder, info.version)
    recordBlockmapVersion(pendingFolder, info.version, platform)
  })
  // Nothing newer to install, say the release was pulled. A download offered
  // this session stays: quitting the app still installs it.
  updater.on("update-not-available", () => {
    if (!offered) queue(() => free(pendingFolder))
  })

  return {
    ...updates,
    check: () => {
      queue(() => dropStaleBlockmap(pendingFolder, installedVersion, platform))
      return tidying.then(() => updates.check())
    },
  }
}

async function freeIfInstalled(pendingFolder: string, installed: string): Promise<void> {
  const downloaded = readDownloadedVersion(pendingFolder)
  // No record: an app from before this one made the download, which this one replaced.
  if (downloaded !== undefined && waitsToInstall(downloaded, installed)) return
  await free(pendingFolder)
}

async function free(pendingFolder: string): Promise<void> {
  // Still held, say by the installer that just ran from it; the next launch retries.
  await rm(pendingFolder, { recursive: true, force: true }).catch(() => undefined)
}

/** Keeps the download unless it is provably not newer, so nothing needed is lost. */
function waitsToInstall(downloaded: string | null, installed: string): boolean {
  const a = release(downloaded)
  const b = release(installed)
  if (a === null || b === null) return true
  for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i]
  // Same x.y.z: only the very same version is known to be installed.
  return downloaded !== installed
}

function release(version: string | null): number[] | null {
  const parts = version?.match(/^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/)
  return parts ? parts.slice(1, 4).map(Number) : null
}
