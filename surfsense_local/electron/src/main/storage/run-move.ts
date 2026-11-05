import { mkdir, readdir, rename, rm, rmdir } from "node:fs/promises"
import { join } from "node:path"

import { readStorageLocation, writeStorageLocation, type StorageLocation } from "./location-file.ts"
import { copyVerified, CopyMismatchError } from "./copy-verified.ts"
import { writeMarker } from "./marker.ts"
import { STAGING_PREFIX, type MovePlan } from "./plan-move.ts"
import { repointDatabases, repointModelConfigs } from "./repoint-paths.ts"
import { scanEntries } from "./scan-entries.ts"

export type MoveProgress = {
  phase: "copying" | "verifying" | "switching"
  doneBytes: number
  totalBytes: number
}

export type MoveFailure = "canceled" | "no_room" | "verify_failed" | "failed"

export class MoveFailedError extends Error {
  readonly reason: MoveFailure
  constructor(reason: MoveFailure, cause?: unknown) {
    super(`the move failed: ${reason}${cause ? ` (${String(cause)})` : ""}`)
    this.reason = reason
  }
}

const PROGRESS_INTERVAL_MS = 100

// Windows antivirus and indexers hold a just-written file for a moment.
async function renameWithRetries(from: string, to: string): Promise<void> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      await rename(from, to)
      return
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (attempt >= 20 || (code !== "EPERM" && code !== "EBUSY" && code !== "EACCES")) throw error
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
}

function nextLocation(
  plan: MovePlan,
  baseDir: string,
  previous: StorageLocation,
): StorageLocation {
  const { kind, fromRoot, toRoot, entries, adopt } = plan
  const { movingTo: _movingTo, leftBehind = [], ...rest } = previous
  const next: StorageLocation = { ...rest }
  if (kind === "data") {
    if (toRoot === baseDir) delete next.dataRoot
    else next.dataRoot = toRoot
  } else if (toRoot === (next.dataRoot ?? baseDir)) {
    delete next.modelsRoot
  } else {
    next.modelsRoot = toRoot
  }
  // A folder being returned to must not be cleaned up by an earlier move's record.
  const kept = leftBehind.filter(({ root }) => root !== toRoot)
  // Switching to files already there leaves the old ones alone: nothing was copied.
  const remaining = adopt ? kept : [...kept, { root: fromRoot, entries }]
  if (remaining.length > 0) next.leftBehind = remaining
  return next
}

function failureFrom(error: unknown): MoveFailedError {
  if (error instanceof MoveFailedError) return error
  if (error instanceof CopyMismatchError) return new MoveFailedError("verify_failed", error)
  const { name, code } = error as NodeJS.ErrnoException
  if (name === "AbortError" || code === "ABORT_ERR") return new MoveFailedError("canceled")
  if (code === "ENOSPC" || code === "EDQUOT") return new MoveFailedError("no_room", error)
  return new MoveFailedError("failed", error)
}

/**
 * Carry the folder over while nothing else is using it. The originals are not
 * touched: the location changes last, in one step, and they are removed only
 * after the next start proves the new folder works.
 */
export async function runMove(options: {
  plan: MovePlan
  baseDir: string
  signal: AbortSignal
  onProgress: (progress: MoveProgress) => void
}): Promise<void> {
  const { plan, baseDir, signal, onProgress } = options
  const { kind, fromRoot, toRoot, entries, adopt } = plan
  const staging = join(toRoot, `${STAGING_PREFIX}${kind}`)
  const placed: string[] = []

  try {
    if (!adopt) {
      writeStorageLocation(baseDir, { ...readStorageLocation(baseDir), movingTo: staging })
      await rm(staging, { recursive: true, force: true, maxRetries: 5 })
      await mkdir(staging, { recursive: true })

      const scan = await scanEntries(fromRoot, entries)
      const totalBytes = scan.totalBytes * 2
      let doneBytes = 0
      let lastReport = 0
      await copyVerified({
        scan,
        fromRoot,
        stagingRoot: staging,
        finalRoot: toRoot,
        signal,
        onBytes: (phase, bytes) => {
          doneBytes += bytes
          const now = Date.now()
          if (now - lastReport < PROGRESS_INTERVAL_MS) return
          lastReport = now
          onProgress({ phase, doneBytes, totalBytes })
        },
      })

      signal.throwIfAborted()
      onProgress({ phase: "switching", doneBytes: totalBytes, totalBytes })
      repointModelConfigs(staging, fromRoot, toRoot)
      if (kind === "data") repointDatabases(staging, fromRoot, toRoot)

      // What is there now: closing a repointed database removes its -wal and -shm.
      for (const entry of await readdir(staging)) {
        const destination = join(toRoot, entry)
        // An empty folder from an earlier run; planMove refused anything that held files.
        await rmdir(destination).catch(() => undefined)
        await renameWithRetries(join(staging, entry), destination)
        placed.push(destination)
      }
      await rm(staging, { recursive: true, force: true, maxRetries: 5 })
    }
    const next = nextLocation(plan, baseDir, readStorageLocation(baseDir))
    // A folder holds one marker, so models returning into the data folder keep its data marker.
    const entersDataFolder = kind === "models" && toRoot === next.dataRoot
    // The default folder needs no proof that it is here: it is where the app starts.
    if (toRoot !== baseDir && !entersDataFolder) writeMarker(toRoot, kind)
    writeStorageLocation(baseDir, next)
  } catch (error) {
    for (const path of placed) await rm(path, { recursive: true, force: true }).catch(() => undefined)
    await rm(staging, { recursive: true, force: true, maxRetries: 5 }).catch(() => undefined)
    const { movingTo: _movingTo, ...location } = readStorageLocation(baseDir)
    writeStorageLocation(baseDir, location)
    throw failureFrom(error)
  }
}

