import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { checkInstallerSizes, readBudgets } from "./check-installer-size.mjs"

const MiB = 1024 * 1024
const SCRIPT = fileURLToPath(new URL("./check-installer-size.mjs", import.meta.url))

/** A release folder holding a file of each given size, in MiB. */
function release(t, sizes) {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-installer-size-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  for (const [name, mib] of Object.entries(sizes)) writeFileSync(join(dir, name), Buffer.alloc(Math.round(mib * MiB)))
  return dir
}

const BUDGETS = {
  "SurfSense-arm64.dmg": { platform: "darwin", maxMiB: 2 },
  "SurfSense-arm64.zip": { platform: "darwin", maxMiB: 3 },
  "SurfSense-Setup.exe": { platform: "win32", maxMiB: 1 },
}

test("installers within their budgets pass, each with its size", (t) => {
  const releaseDir = release(t, { "SurfSense-arm64.dmg": 1.5, "SurfSense-arm64.zip": 3 })
  const { rows, failed } = checkInstallerSizes({ releaseDir, budgets: BUDGETS, platform: "darwin" })

  assert.equal(failed, false)
  assert.deepEqual(
    rows.map(({ name, sizeMiB, maxMiB, status }) => ({ name, sizeMiB, maxMiB, status })),
    [
      { name: "SurfSense-arm64.dmg", sizeMiB: 1.5, maxMiB: 2, status: "ok" },
      { name: "SurfSense-arm64.zip", sizeMiB: 3, maxMiB: 3, status: "ok" },
    ]
  )
})

test("an installer over its budget fails the check", (t) => {
  const releaseDir = release(t, { "SurfSense-arm64.dmg": 2.01, "SurfSense-arm64.zip": 1 })
  const { rows, failed } = checkInstallerSizes({ releaseDir, budgets: BUDGETS, platform: "darwin" })

  assert.equal(failed, true)
  assert.equal(rows.find((row) => row.name === "SurfSense-arm64.dmg").status, "over")
})

test("an installer this OS should have built but did not fails the check, so a renamed one is not skipped", (t) => {
  const releaseDir = release(t, { "SurfSense-arm64.dmg": 1 })
  const { rows, failed } = checkInstallerSizes({ releaseDir, budgets: BUDGETS, platform: "darwin" })

  assert.equal(failed, true)
  assert.equal(rows.find((row) => row.name === "SurfSense-arm64.zip").status, "missing")
})

test("only this OS's installers are checked", (t) => {
  const releaseDir = release(t, { "SurfSense-Setup.exe": 0.5 })
  const { rows, failed } = checkInstallerSizes({ releaseDir, budgets: BUDGETS, platform: "win32" })

  assert.equal(failed, false)
  assert.deepEqual(rows.map((row) => row.name), ["SurfSense-Setup.exe"])
})

test("an OS with no budget at all fails rather than checking nothing", (t) => {
  const releaseDir = release(t, {})
  assert.throws(() => checkInstallerSizes({ releaseDir, budgets: BUDGETS, platform: "freebsd" }), /freebsd/)
})

test("the budgets cover every installer the release builds, on its own OS", () => {
  const budgets = readBudgets()
  assert.deepEqual(
    Object.entries(budgets).map(([name, { platform }]) => [name, platform]).sort(),
    [
      ["SurfSense-Setup.exe", "win32"],
      ["SurfSense-arm64.dmg", "darwin"],
      ["SurfSense-arm64.zip", "darwin"],
      ["SurfSense.AppImage", "linux"],
      ["SurfSense.deb", "linux"],
      ["SurfSense.rpm", "linux"],
    ].sort()
  )
  for (const { maxMiB } of Object.values(budgets)) assert.ok(maxMiB > 0)
})

test("the budgeted names are the ones electron-builder.yml gives the installers", () => {
  const yml = readFileSync(new URL("../electron-builder.yml", import.meta.url), "utf8").replace(/\r\n/g, "\n")
  const productName = yml.match(/^productName: (\S+)$/m)[1]
  const named = []
  for (const os of ["win", "mac", "linux"]) {
    const section = yml.match(new RegExp(`^${os}:\\n((?:[ \\t]+.*\\n|\\n)*)`, "m"))[1]
    const pattern = section.match(/^  artifactName: "(.+)"$/m)[1]
    // Read from each target list, so a target added there without a budget fails here.
    // Each file's extension is its target's name, NSIS's .exe aside.
    const exts = section.match(/^  target: \[(.+)\]$/m)[1].split(/,\s*/).map((target) => (target === "nsis" ? "exe" : target))
    // The release builds macOS for Apple Silicon only (ADR 0021).
    for (const ext of exts) named.push(pattern.replace("${productName}", productName).replace("${arch}", "arm64").replace("${ext}", ext))
  }
  assert.deepEqual(named.sort(), Object.keys(readBudgets()).sort())
})

test("run as a script, it prints every size and exits non-zero when one is over", (t) => {
  const releaseDir = release(t, { "SurfSense-Setup.exe": 0.25 })
  const budgetsFile = join(releaseDir, "budgets.json")
  writeFileSync(budgetsFile, JSON.stringify({ "SurfSense-Setup.exe": { platform: process.platform, maxMiB: 0.5 } }))

  const passed = execFileSync(process.execPath, [SCRIPT, releaseDir, budgetsFile], { encoding: "utf8" })
  assert.match(passed, /SurfSense-Setup\.exe\s+0\.3 MiB\s+of 0\.5 MiB/)

  writeFileSync(budgetsFile, JSON.stringify({ "SurfSense-Setup.exe": { platform: process.platform, maxMiB: 0.1 } }))
  assert.throws(
    () => execFileSync(process.execPath, [SCRIPT, releaseDir, budgetsFile], { encoding: "utf8", stdio: "pipe" }),
    (error) => error.status === 1 && /over budget/.test(error.stdout + error.stderr)
  )
})
