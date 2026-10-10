// Where each generator leaves its fragment and where the merged notices land,
// which electron-builder ships as resources/notices.
import { mkdirSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

export const NOTICES_DIR = fileURLToPath(new URL("../../notices", import.meta.url))
export const FRAGMENTS_DIR = join(NOTICES_DIR, "fragments")

// One per generator; the merge refuses to run while any is missing.
export const FRAGMENTS = ["npm-frontend", "npm-electron", "python", "native", "models"]

export function writeFragment(name, fragment) {
  mkdirSync(FRAGMENTS_DIR, { recursive: true })
  const path = join(FRAGMENTS_DIR, `${name}.json`)
  writeFileSync(path, `${JSON.stringify(fragment, null, 2)}\n`)
  return path
}
