import type { PlatformPath } from "node:path"
import path from "node:path"

import type { StorageKind } from "./marker.ts"

const FOLDER_NAMES: Record<StorageKind, string> = {
  data: "SurfSense-Data",
  models: "SurfSense-Models",
}

export type TargetRefusal = "same_folder" | "inside_current" | "inside_app" | "network_drive"

/** The app's own subfolder of what was picked, so nothing of the user's is ever in the way. */
export function targetRoot(
  kind: StorageKind,
  picked: string,
  pickedIsMarked: boolean,
  paths: PlatformPath = path
): string {
  if (pickedIsMarked || paths.basename(picked) === FOLDER_NAMES[kind]) return picked
  return paths.join(picked, FOLDER_NAMES[kind])
}

// `relative` folds case on Windows, which a plain prefix test would miss.
function isWithin(parent: string, child: string, paths: PlatformPath): boolean {
  const relative = paths.relative(parent, child)
  return relative === "" || (!relative.startsWith("..") && !paths.isAbsolute(relative))
}

export function refusalForTarget(options: {
  kind: StorageKind
  root: string
  baseDir: string
  dataRoot: string
  modelsRoot: string
  appFolder: string
  paths?: PlatformPath
}): TargetRefusal | null {
  const { kind, root, baseDir, dataRoot, modelsRoot, appFolder, paths = path } = options
  const current = kind === "data" ? dataRoot : modelsRoot
  if (paths.relative(current, root) === "") return "same_folder"
  if (isWithin(appFolder, root, paths)) return "inside_app"
  for (const folder of [baseDir, dataRoot, modelsRoot]) {
    if (isWithin(folder, root, paths)) return "inside_current"
  }
  // SQLite's locks do not hold on a share; models are only read and written whole.
  if (kind === "data" && paths.sep === "\\" && root.startsWith("\\\\")) return "network_drive"
  return null
}

