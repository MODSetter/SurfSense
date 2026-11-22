// What an opencode folder must hold, and proof that it runs. stage.mjs checks
// its stage before the swap, and after-sign.mjs the signed copy before any
// installer is made, because signing can break an executable. Release CI checks
// the folder each installer carries:
//   node ../runtimes/opencode/check-stage.mjs <folder>
import { execFileSync } from "node:child_process"
import { existsSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
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
export function versionOf(binary, env = process.env) {
  try {
    return execFileSync(binary, ["--version"], { encoding: "utf8", env, timeout: 60_000, windowsHide: true }).trim()
  } catch {
    return null
  }
}

/**
 * What opencode says its version is, run in a throwaway home: 2.x writes a log
 * even for --version, and Bun leaves files in the temp folder at every start.
 */
export function opencodeVersionOf(binary) {
  const home = mkdtempSync(join(tmpdir(), "surfsense-opencode-version-"))
  try {
    return versionOf(binary, {
      ...process.env,
      HOME: home,
      USERPROFILE: home,
      OPENCODE_TEST_HOME: home,
      XDG_CONFIG_HOME: join(home, "config"),
      XDG_DATA_HOME: join(home, "data"),
      XDG_CACHE_HOME: join(home, "cache"),
      XDG_STATE_HOME: join(home, "state"),
      TMPDIR: home,
      TEMP: home,
      TMP: home,
    })
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
}

/** The release in opencode's `opencode v2.1.2`, or null for anything else. */
function releaseIn(said) {
  return said?.match(/^opencode v(\S+)$/)?.[1] ?? null
}

/** Throws unless `folder` holds both executables and their licences, and each runs as its pin. */
export function checkStage(folder) {
  const missing = REQUIRED.filter((name) => !existsSync(join(folder, name)))
  if (missing.length) throw new Error(`${folder} lacks ${missing.join(", ")}`)
  const opencode = opencodeVersionOf(join(folder, OPENCODE))
  if (releaseIn(opencode) !== VERSION) throw new Error(`opencode in ${folder} says ${opencode}, expected ${VERSION}`)
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
