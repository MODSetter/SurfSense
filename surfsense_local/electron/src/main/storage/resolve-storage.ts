import type { StorageLocation } from "./location-file.ts"
import { hasMarker } from "./marker.ts"

export type ResolvedStorage = {
  /** Never moves: Electron's settings and the location file. */
  baseDir: string
  dataRoot: string
  modelsRoot: string
  dataMoved: boolean
  modelsMoved: boolean
  dataReachable: boolean
  modelsReachable: boolean
}

export function resolveStorage(baseDir: string, location: StorageLocation): ResolvedStorage {
  const dataRoot = location.dataRoot ?? baseDir
  const modelsRoot = location.modelsRoot ?? dataRoot
  return {
    baseDir,
    dataRoot,
    modelsRoot,
    dataMoved: location.dataRoot !== undefined,
    modelsMoved: location.modelsRoot !== undefined,
    dataReachable: location.dataRoot === undefined || hasMarker(location.dataRoot, "data"),
    modelsReachable: location.modelsRoot === undefined
      ? location.dataRoot === undefined || hasMarker(location.dataRoot, "data")
      : hasMarker(location.modelsRoot, "models"),
  }
}
