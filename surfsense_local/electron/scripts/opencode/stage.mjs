// `pnpm build:opencode`: stage the pinned opencode and the ripgrep it greps
// with into electron/opencode, swapped in whole once both report their versions.
// The installer downloads nothing, so this is the only fetch either one gets.
import { execFileSync } from "node:child_process"
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, renameSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { basename, join } from "node:path"
import { fileURLToPath } from "node:url"

import { download, unpack } from "../pinned-download.mjs"
import { renameWhenUnlocked } from "../windows-locks/rename-when-unlocked.mjs"
import { opencodeEnabled } from "./enabled.mjs"
import { HOSTS, OPENCODE_LICENCE, RIPGREP_VERSION, VERSION } from "./pins.mjs"

const OUT = fileURLToPath(new URL("../../opencode", import.meta.url))
const windows = process.platform === "win32"
const OPENCODE = windows ? "opencode.exe" : "opencode"
const RG = windows ? "rg.exe" : "rg"
// ripgrep is dual-licensed MIT or Unlicense; COPYING says so, and all three ship.
const RIPGREP_LICENCES = ["COPYING", "LICENSE-MIT", "UNLICENSE"]

/** The first file under `root` called `name`, wherever the archive nests it. */
function find(root, name) {
  for (const entry of readdirSync(root, { withFileTypes: true, recursive: true })) {
    if (entry.isFile() && entry.name === name) return join(entry.parentPath, entry.name)
  }
  throw new Error(`no ${name} in ${root}`)
}

/** What a staged executable says its version is, or null when it will not run. */
function versionOf(binary, args = ["--version"]) {
  try {
    return execFileSync(binary, args, { encoding: "utf8", timeout: 60_000, windowsHide: true }).trim()
  } catch {
    return null
  }
}

/** Download one pinned archive and unpack it into its own folder under `work`. */
async function fetchArchive(pin, work) {
  const archive = join(work, basename(new URL(pin.url).pathname))
  const into = `${archive}.unpacked`
  console.log(`downloading ${pin.url}`)
  await download(pin, archive)
  mkdirSync(into)
  unpack(archive, into)
  return into
}

/** Copy one executable into the stage, runnable on macOS and Linux. */
function copyExecutable(from, to) {
  copyFileSync(from, to)
  if (!windows) chmodSync(to, 0o755)
}

/** Prove the stage runs: the server is the pinned release, and so is ripgrep. */
function verifyStage(stage) {
  const opencode = versionOf(join(stage, OPENCODE))
  if (opencode !== VERSION) throw new Error(`staged opencode says ${opencode}, expected ${VERSION}`)
  const ripgrep = versionOf(join(stage, RG)) ?? ""
  if (!ripgrep.startsWith(`ripgrep ${RIPGREP_VERSION}`)) {
    throw new Error(`staged ripgrep says ${ripgrep}, expected ${RIPGREP_VERSION}`)
  }
}

async function main() {
  // Off also removes an earlier stage, so neither a dev run nor an installer carries one.
  if (!opencodeEnabled()) {
    rmSync(OUT, { recursive: true, force: true })
    console.log("opencode is off: SURFSENSE_LOCAL_OPENCODE_ENABLED=0 stages nothing")
    return
  }

  const host = `${process.platform}-${process.arch}`
  const pins = HOSTS[host]
  if (!pins) throw new Error(`no opencode build is pinned for ${host}`)

  // A staged build of another release would leave the backend speaking to an
  // API it was not written for, so a version bump restages.
  if (versionOf(join(OUT, OPENCODE)) === VERSION && existsSync(join(OUT, RG))) {
    console.log(`opencode ${VERSION} already staged in ${OUT}`)
    return
  }

  const work = mkdtempSync(join(tmpdir(), "surfsense-opencode-"))
  const stage = `${OUT}.stage-${process.pid}`
  const backup = `${OUT}.old-${process.pid}`
  try {
    mkdirSync(stage, { recursive: true })

    const opencode = await fetchArchive(pins.opencode, work)
    copyExecutable(find(opencode, OPENCODE), join(stage, OPENCODE))
    await download(OPENCODE_LICENCE, join(stage, "LICENSE"))

    const ripgrep = await fetchArchive(pins.ripgrep, work)
    copyExecutable(find(ripgrep, RG), join(stage, RG))
    mkdirSync(join(stage, "ripgrep"))
    for (const licence of RIPGREP_LICENCES) {
      copyFileSync(find(ripgrep, licence), join(stage, "ripgrep", licence))
    }

    verifyStage(stage)

    rmSync(backup, { recursive: true, force: true })
    if (existsSync(OUT)) renameSync(OUT, backup)
    try {
      await renameWhenUnlocked(stage, OUT)
    } catch (error) {
      if (existsSync(backup)) renameSync(backup, OUT)
      throw error
    }
    rmSync(backup, { recursive: true, force: true })
    console.log(`opencode ${VERSION} and ripgrep ${RIPGREP_VERSION} staged in ${OUT}`)
  } finally {
    rmSync(stage, { recursive: true, force: true })
    rmSync(work, { recursive: true, force: true })
  }
}

await main()
