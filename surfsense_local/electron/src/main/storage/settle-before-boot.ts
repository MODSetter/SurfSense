
import { readStorageLocation, writeStorageLocation } from "./location-file.ts"
import { hasMarker } from "./marker.ts"
import { resolveStorage, type ResolvedStorage } from "./resolve-storage.ts"
import { targetRoot } from "./target-folder.ts"

export type DrivePrompts = {
  dataMissing: (path: string) => Promise<"retry" | "choose" | "quit">
  modelsMissing: (path: string) => Promise<"retry" | "continue" | "quit">
  pickDataFolder: () => Promise<string | null>
  notADataFolder: (path: string) => Promise<void>
}

export type SettledStorage = { storage: ResolvedStorage; modelsUnavailable: boolean }

/**
 * Where this run's data and models are, asking the user when a drive is away.
 * Null means quit. Nothing may start before this: an API on an empty folder
 * would make a fresh database, which looks like the user's data is gone.
 */
export async function settleStorageBeforeBoot(
  baseDir: string,
  prompts: DrivePrompts,
): Promise<SettledStorage | null> {
  for (;;) {
    const location = readStorageLocation(baseDir)
    const storage = resolveStorage(baseDir, location)

    if (!storage.dataReachable) {
      const answer = await prompts.dataMissing(storage.dataRoot)
      if (answer === "quit") return null
      if (answer === "choose") {
        const picked = await prompts.pickDataFolder()
        if (picked !== null) {
          const root = targetRoot("data", picked, hasMarker(picked, "data"))
          if (hasMarker(root, "data")) writeStorageLocation(baseDir, { ...location, dataRoot: root })
          else await prompts.notADataFolder(picked)
        }
      }
      continue
    }

    if (!storage.modelsReachable) {
      const answer = await prompts.modelsMissing(storage.modelsRoot)
      if (answer === "quit") return null
      if (answer === "continue") return { storage, modelsUnavailable: true }
      continue
    }

    return { storage, modelsUnavailable: false }
  }
}

