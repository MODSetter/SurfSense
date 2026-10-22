import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

/** The `nsis:` section of electron-builder.yml, as key: value pairs. */
function nsisSection() {
  const yml = readFileSync(new URL("../electron-builder.yml", import.meta.url), "utf8")
  const block = yml.match(/^nsis:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  return Object.fromEntries(
    [...block.matchAll(/^  (\w+): (.+)$/gm)].map(([, key, value]) => [key, value.trim()]),
  )
}

test("the Windows installer lets the user pick its folder", () => {
  // The one-click default installs into %LOCALAPPDATA%\Programs with no choice (#2288).
  const nsis = nsisSection()
  assert.equal(nsis.oneClick, "false")
  assert.equal(nsis.allowToChangeInstallationDirectory, "true")
})

test("the Windows installer still installs for the current user only", () => {
  // Per machine would ask for elevation, and every update after it too.
  assert.equal(nsisSection().perMachine, "false")
})
