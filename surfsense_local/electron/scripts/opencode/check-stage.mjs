// What an opencode folder must hold, and proof that it runs. stage.mjs checks
// its stage before the swap; release CI checks the folder each installer
// carries, signed where the build is, because signing can break an executable:
//   node scripts/opencode/check-stage.mjs <folder>
import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { RIPGREP_VERSION, VERSION } from "./pins.mjs"

const windows = process.platform === "win32"
export const OPENCODE = windows ? "opencode.exe" : "opencode"
export const RG = windows ? "rg.exe" : "rg"
// ripgrep is dual-licensed MIT or Unlicense; COPYING says so, and all three ship.
export const RIPGREP_LICENCES = ["COPYING", "LICENSE-MIT", "UNLICENSE"]

const REQUIRED = [OPENCODE, RG, "LICENSE", ...RIPGREP_LICENCES.map((name) => join("ripgrep", name))]

/** What an executable says its version is, or null when it will not run. */
export function versionOf(binary) {
  try {
    return execFileSync(binary, ["--version"], { encoding: "utf8", timeout: 60_000, windowsHide: true }).trim()
  } catch {
    return null
  }
}

/** Throws unless `folder` holds both executables and their licences, and each runs as its pin. */
export function checkStage(folder) {
  const missing = REQUIRED.filter((name) => !existsSync(join(folder, name)))
  if (missing.length) throw new Error(`${folder} lacks ${missing.join(", ")}`)
  const opencode = versionOf(join(folder, OPENCODE))
  if (opencode !== VERSION) throw new Error(`opencode in ${folder} says ${opencode}, expected ${VERSION}`)
  const ripgrep = versionOf(join(folder, RG)) ?? ""
  if (!ripgrep.startsWith(`ripgrep ${RIPGREP_VERSION}`)) {
    throw new Error(`ripgrep in ${folder} says ${ripgrep}, expected ${RIPGREP_VERSION}`)
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const folder = process.argv[2]
  if (!folder) throw new Error("usage: check-stage.mjs <folder>")
  checkStage(folder)
  console.log(`opencode ${VERSION} and ripgrep ${RIPGREP_VERSION} run from ${folder}`)
}
