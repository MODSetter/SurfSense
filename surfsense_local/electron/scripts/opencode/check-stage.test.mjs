import assert from "node:assert/strict"
import {
  chmodSync,
  copyFileSync,
  existsSync,
  linkSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs"
import { homedir, tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { checkStage, OPENCODE, RG, RIPGREP_LICENCES } from "./check-stage.mjs"
import { RIPGREP_VERSION, VERSION } from "./pins.mjs"

function folder(t) {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-opencode-check-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

/** Every file a stage holds, each empty, less the ones named. */
function holding(dir, ...left) {
  mkdirSync(join(dir, "ripgrep"))
  const files = [OPENCODE, RG, "LICENSE", ...RIPGREP_LICENCES.map((name) => join("ripgrep", name))]
  for (const name of files.filter((name) => !left.includes(name))) writeFileSync(join(dir, name), "")
}

/** Node under opencode's name: it runs, and says a version that is not the pin. */
function nodeAsOpencode(dir) {
  const to = join(dir, OPENCODE)
  rmSync(to, { force: true })
  try {
    if (process.platform === "win32") linkSync(process.execPath, to)
    else symlinkSync(process.execPath, to)
  } catch {
    copyFileSync(process.execPath, to)
  }
}

/** A shell script under `name` that prints `line`, noting the home it was given. */
function script(dir, name, line) {
  const to = join(dir, name)
  writeFileSync(
    to,
    [
      "#!/bin/sh",
      'mkdir -p "$XDG_DATA_HOME/opencode/log" && touch "$XDG_DATA_HOME/opencode/log/version.log"',
      `printf '%s\\n' "$HOME" > "${to}.home"`,
      `echo "${line}"`,
    ].join("\n")
  )
  chmodSync(to, 0o755)
}

// Scripts stand in for the executables; Windows runs only .exe under these names.
const posix = { skip: process.platform === "win32" && "needs an executable script" }

test("a stage of the pinned release passes, its version log written in a throwaway home", posix, (t) => {
  // 2.x writes a log even for --version, which must not land in the user's own opencode.
  const dir = folder(t)
  holding(dir)
  script(dir, OPENCODE, `opencode v${VERSION}`)
  script(dir, RG, `ripgrep ${RIPGREP_VERSION} (rev abc)`)

  checkStage(dir)

  const home = readFileSync(join(dir, `${OPENCODE}.home`), "utf8").trim()
  assert.notEqual(home, homedir())
  assert.equal(existsSync(home), false)
})

test("an opencode of another 2.x release fails the check", posix, (t) => {
  const dir = folder(t)
  holding(dir)
  script(dir, OPENCODE, "opencode v2.1.1")
  assert.throws(() => checkStage(dir), new RegExp(`says opencode v2\\.1\\.1, expected ${VERSION}$`))
})

test("an installer with no opencode in it fails the check", (t) => {
  const dir = folder(t)
  assert.throws(() => checkStage(dir), new RegExp(`lacks ${OPENCODE}, ${RG}, LICENSE`))
})

test("a missing licence fails the check before anything runs", (t) => {
  const dir = folder(t)
  holding(dir, join("ripgrep", "UNLICENSE"))
  assert.throws(() => checkStage(dir), /lacks ripgrep.UNLICENSE$/)
})

test("an opencode that is not the pinned release fails the check", (t) => {
  const dir = folder(t)
  holding(dir)
  nodeAsOpencode(dir)
  assert.throws(
    () => checkStage(dir),
    (error) => error.message.endsWith(`says ${process.version}, expected ${VERSION}`)
  )
})
