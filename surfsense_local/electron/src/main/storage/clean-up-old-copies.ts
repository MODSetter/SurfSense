import { existsSync } from "node:fs"
import { rm, rmdir } from "node:fs/promises"
import { join } from "node:path"

import { readStorageLocation, writeStorageLocation } from "./location-file.ts"
import { MARKER_FILE } from "./marker.ts"

/** A crash's partial copy, found from the record made before it began. */
export async function removeInterruptedCopy(baseDir: string): Promise<void> {
  const { movingTo, ...location } = readStorageLocation(baseDir)
  if (movingTo === undefined) return
  await rm(movingTo, { recursive: true, force: true, maxRetries: 5 }).catch(() => undefined)
  writeStorageLocation(baseDir, location)
}

/**
 * Called once this start's API has answered from the new folder, so a move that
 * did not work still has its original. Removes only what the move named: the old
 * folder may be the user's home or hold anything else.
 */
export async function removeOldCopies(baseDir: string): Promise<void> {
  const location = readStorageLocation(baseDir)
  const { leftBehind = [], ...rest } = location
  if (leftBehind.length === 0) return
  // A drive that is away keeps its record for a later start.
  const waiting = []
  for (const old of leftBehind) {
    if (!existsSync(old.root)) {
      waiting.push(old)
      continue
    }
    for (const entry of old.entries) {
      await rm(join(old.root, entry), { recursive: true, force: true, maxRetries: 5 }).catch(() => undefined)
    }
    // Models can leave the data folder, which stays in use and still needs its marker.
    if (old.root !== baseDir && old.root !== rest.dataRoot && old.root !== rest.modelsRoot) {
      await rm(join(old.root, MARKER_FILE), { force: true }).catch(() => undefined)
      await rmdir(old.root).catch(() => undefined)
    }
  }
  writeStorageLocation(baseDir, { ...rest, ...(waiting.length > 0 && { leftBehind: waiting }) })
}
