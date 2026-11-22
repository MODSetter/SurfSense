import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"

export type StorageKind = "data" | "models"

export const MARKER_FILE = ".surfsense-storage"

/**
 * Proves this is the real folder, not the empty mount point a disconnected
 * drive leaves on Linux, which would otherwise accept writes on the wrong disk.
 */
export function hasMarker(root: string, kind: StorageKind): boolean {
  try {
    return JSON.parse(readFileSync(join(root, MARKER_FILE), "utf8")).kind === kind
  } catch {
    return false
  }
}

export function writeMarker(root: string, kind: StorageKind): void {
  writeFileSync(join(root, MARKER_FILE), JSON.stringify({ kind }))
}
