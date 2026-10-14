import assert from "node:assert/strict"
import { copyFileSync, linkSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { checkStage, OPENCODE, RG, RIPGREP_LICENCES } from "./check-stage.mjs"
import { VERSION } from "./pins.mjs"

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
