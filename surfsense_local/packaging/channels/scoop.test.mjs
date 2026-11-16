import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { publishedRelease } from "./release.mjs"
import { scoopManifest } from "./scoop.mjs"

const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))
const release = publishedRelease(JSON.parse(readFileSync(FIXTURE, "utf8")), "2.3.0")
const text = scoopManifest(release)["surfsense.json"]
const manifest = JSON.parse(text)

test("unpacks this tag's NSIS installer, checked by GitHub's digest", () => {
  assert.equal(manifest.version, "2.3.0")
  assert.equal(manifest.license, "Apache-2.0")
  assert.equal(manifest.homepage, "https://www.surfsense.com")
  assert.deepEqual(manifest.architecture["64bit"], {
    url: "https://github.com/MODSetter/SurfSense/releases/download/v2.3.0/SurfSense-Setup.exe#/dl.7z",
    hash: "c".repeat(64),
    pre_install: 'Expand-7zipArchive "$dir\\`$PLUGINSDIR\\app-64.7z" "$dir"',
  })
  assert.deepEqual(manifest.shortcuts, [["SurfSense.exe", "SurfSense"]])
  // Data lives in ~/.surfsense, outside the app folder Scoop replaces.
  assert.equal(manifest.persist, undefined)
})

test("Excavator finds new versions and their hashes without downloading the installer", () => {
  assert.deepEqual(manifest.checkver, { github: "https://github.com/MODSetter/SurfSense" })
  assert.deepEqual(manifest.autoupdate, {
    architecture: {
      "64bit": {
        url: "https://github.com/MODSetter/SurfSense/releases/download/v$version/SurfSense-Setup.exe#/dl.7z",
      },
    },
  })
  // With no hash block, Scoop reads the release asset's GitHub digest.
  assert.equal(manifest.autoupdate.hash, undefined)
})

test("is formatted as Extras manifests are: four spaces, one trailing newline", () => {
  assert.equal(text, `${JSON.stringify(manifest, null, 4)}\n`)
})

/** A Windows PowerShell that runs, or Scoop's own fallback. */
const powershell = ["powershell", "pwsh"].find(
  (name) =>
    spawnSync(name, ["-NoProfile", "-NonInteractive", "-Command", "'ok'"], { encoding: "utf8", timeout: 60_000 })
      .stdout?.trim() === "ok"
)

test(
  "install leaves the app marked as Scoop's, without the NSIS leftovers or electron-updater's feed",
  { skip: process.platform !== "win32" ? "Scoop runs on Windows" : !powershell && "needs PowerShell" },
  (t) => {
    const root = mkdtempSync(join(tmpdir(), "surfsense-scoop-"))
    t.after(() => rmSync(root, { recursive: true, force: true }))
    // What 7-Zip leaves in $dir from SurfSense-Setup.exe, plus the unpacked app.
    const dir = join(root, "2.3.0")
    mkdirSync(join(dir, "$PLUGINSDIR"), { recursive: true })
    writeFileSync(join(dir, "$PLUGINSDIR", "app-64.7z"), "")
    writeFileSync(join(dir, "$R0"), "")
    writeFileSync(join(dir, "Uninstall SurfSense.exe"), "")
    mkdirSync(join(dir, "resources"))
    writeFileSync(join(dir, "resources", "app-update.yml"), "provider: github\n")
    writeFileSync(join(dir, "SurfSense.exe"), "")

    const scripts = [manifest.architecture["64bit"].pre_install, ...manifest.post_install]
    const script = join(root, "install.ps1")
    writeFileSync(
      script,
      [
        "$ErrorActionPreference = 'Stop'",
        `$dir = '${dir}'`,
        // Scoop's helper; this records what it was asked to unpack.
        "function Expand-7zipArchive($Path, $DestinationPath) { Set-Content -Path (Join-Path $dir 'expanded.txt') -Value \"$Path|$DestinationPath\" -NoNewline }",
        ...scripts,
      ].join("\r\n")
    )
    const run = spawnSync(powershell, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script], {
      encoding: "utf8",
      timeout: 60_000,
    })
    assert.equal(run.status, 0, run.stderr || run.stdout)

    assert.equal(readFileSync(join(dir, "expanded.txt"), "utf8"), `${dir}\\$PLUGINSDIR\\app-64.7z|${dir}`)
    assert.equal(readFileSync(join(dir, "resources", "install-channel"), "utf8"), "scoop")
    for (const gone of ["$PLUGINSDIR", "$R0", "Uninstall SurfSense.exe", join("resources", "app-update.yml")]) {
      assert.ok(!existsSync(join(dir, gone)), gone)
    }
    assert.ok(existsSync(join(dir, "SurfSense.exe")))
  }
)
