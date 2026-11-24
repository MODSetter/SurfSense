import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { isAbsolute, join } from "node:path"

// Beside `electron/`, in the folder that never moves: it says where everything else went.
export const LOCATION_FILE = "storage-location.json"

export type LeftBehind = { root: string; entries: string[] }

export type StorageLocation = {
  dataRoot?: string
  modelsRoot?: string
  /** The old copies, removed only once a start has proved the new folder works. */
  leftBehind?: LeftBehind[]
  /** A move in progress, so a crash's partial copy is found and removed at the next start. */
  movingTo?: string
}

const absolute = (value: unknown): value is string =>
  typeof value === "string" && isAbsolute(value)

// A name that could climb out of its root must never reach a delete.
const bareName = (value: unknown): value is string =>
  typeof value === "string" && value !== "" && value !== "." && value !== ".." && !/[\\/]/.test(value)

function leftBehindFrom(value: unknown): LeftBehind[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!absolute(item?.root) || !Array.isArray(item?.entries)) return []
    return [{ root: item.root as string, entries: (item.entries as unknown[]).filter(bareName) }]
  })
}

export function readStorageLocation(baseDir: string): StorageLocation {
  let raw: Record<string, unknown>
  try {
    raw = JSON.parse(readFileSync(join(baseDir, LOCATION_FILE), "utf8"))
  } catch {
    return {}
  }
  const leftBehind = leftBehindFrom(raw?.leftBehind)
  return {
    ...(absolute(raw?.dataRoot) && { dataRoot: raw.dataRoot }),
    ...(absolute(raw?.modelsRoot) && { modelsRoot: raw.modelsRoot }),
    ...(leftBehind.length > 0 && { leftBehind }),
    ...(absolute(raw?.movingTo) && { movingTo: raw.movingTo }),
  }
}

/** Replaced in one step, so a crash leaves the old location or the new one, never half. */
export function writeStorageLocation(baseDir: string, location: StorageLocation): void {
  const path = join(baseDir, LOCATION_FILE)
  const temporary = `${path}.tmp`
  writeFileSync(temporary, JSON.stringify(location, null, 2))
  renameSync(temporary, path)
}
