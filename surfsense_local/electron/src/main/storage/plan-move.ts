import { existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

import { MODEL_FOLDER_NAMES } from "../../../../sidecars/model-folders.ts"
import { LOCATION_FILE } from "./location-file.ts"
import { hasMarker, MARKER_FILE, type StorageKind } from "./marker.ts"
import { probeFolder, type ProbeRefusal } from "./probe-folder.ts"
import type { ResolvedStorage } from "./resolve-storage.ts"
import { scanEntries } from "./scan-entries.ts"
import { refusalForTarget, targetRoot, type TargetRefusal } from "./target-folder.ts"

// Left free after the move, as a download leaves: a full disk takes the database with it.
export const HEADROOM_BYTES = 1024 ** 3

export const STAGING_PREFIX = ".incoming-"
export const UNAVAILABLE_STANDIN = ".models-unavailable"

export type MoveRefusal = TargetRefusal | ProbeRefusal | "not_enough_room" | "target_occupied"

export type MovePlan = {
  kind: StorageKind
  fromRoot: string
  toRoot: string
  entries: string[]
  neededBytes: number
  freeBytes: number
  /** The folder already holds this kind's files: switch to them, copy nothing. */
  adopt: boolean
}

export type PlanResult =
  | { plan: MovePlan }
  | { refused: MoveRefusal; neededBytes?: number; freeBytes?: number }

// What stays behind when the data folder moves: Electron holds these open, and
// the location file has to be found before anything else is known.
const NEVER_MOVES = new Set([
  "electron",
  LOCATION_FILE,
  `${LOCATION_FILE}.tmp`,
  MARKER_FILE,
  "api-url",
  UNAVAILABLE_STANDIN,
])

function namesIn(root: string): string[] {
  try {
    return readdirSync(root)
  } catch {
    return []
  }
}

export function entriesToMove(kind: StorageKind, root: string): string[] {
  const names = namesIn(root)
  if (kind === "models") {
    return MODEL_FOLDER_NAMES.filter((name) => names.includes(name))
  }
  return names.filter((name) => !NEVER_MOVES.has(name) && !name.startsWith(STAGING_PREFIX))
}

const holdsAnything = (path: string): boolean => namesIn(path).length > 0

function holdsThisKindsFiles(kind: StorageKind, root: string): boolean {
  if (kind === "models") return MODEL_FOLDER_NAMES.some((name) => holdsAnything(join(root, name)))
  return existsSync(join(root, "surfsense.db"))
}

/**
 * Where a move would go and whether it can, with nothing changed yet. `picked`
 * null means back to where it lives by default.
 */
export async function planMove(options: {
  kind: StorageKind
  picked: string | null
  storage: ResolvedStorage
  appFolder: string
}): Promise<PlanResult> {
  const { kind, picked, storage, appFolder } = options
  const fromRoot = kind === "data" ? storage.dataRoot : storage.modelsRoot
  const toDefault = picked === null
  const defaultRoot = kind === "data" ? storage.baseDir : storage.dataRoot
  const toRoot = toDefault
    ? defaultRoot
    : targetRoot(kind, picked, hasMarker(picked, kind))

  if (!toDefault) {
    const refused = refusalForTarget({ kind, root: toRoot, ...storage, appFolder })
    if (refused) return { refused }
  } else if (fromRoot === toRoot) {
    return { refused: "same_folder" }
  }

  const probed = await probeFolder(toRoot, kind)
  if ("refused" in probed) return { refused: probed.refused }
  const { freeBytes } = probed

  const entries = entriesToMove(kind, fromRoot)
  const adopt = hasMarker(toRoot, kind) || (toDefault && holdsThisKindsFiles(kind, toRoot))
  if (adopt) return { plan: { kind, fromRoot, toRoot, entries, neededBytes: 0, freeBytes, adopt } }

  // Anything else already in the way would be merged with what moves.
  const inTheWay = entriesToMove(kind, toRoot).some((name) => holdsAnything(join(toRoot, name)) || !isFolder(toRoot, name))
  if (!toDefault && inTheWay) return { refused: "target_occupied" }

  const { totalBytes } = await scanEntries(fromRoot, entries)
  const neededBytes = totalBytes + HEADROOM_BYTES
  if (freeBytes < neededBytes) return { refused: "not_enough_room", neededBytes, freeBytes }
  return { plan: { kind, fromRoot, toRoot, entries, neededBytes, freeBytes, adopt } }
}

function isFolder(root: string, name: string): boolean {
  try {
    readdirSync(join(root, name))
    return true
  } catch {
    return false
  }
}
