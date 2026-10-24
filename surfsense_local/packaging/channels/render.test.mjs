import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, relative } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

// Run with: node --test "surfsense_local/packaging/channels/*.test.mjs"
// Every run reads the fixture through --assets, so nothing here reaches the network.

const RENDER = fileURLToPath(new URL("./render.mjs", import.meta.url))
const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))

function scratch(t) {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-render-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

function render(...args) {
  return spawnSync(process.execPath, [RENDER, ...args], { encoding: "utf8", timeout: 60_000 })
}

/** Every file under `dir`, as forward-slash paths relative to it. */
function filesUnder(dir) {
  if (!existsSync(dir)) return []
  return readdirSync(dir, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => relative(dir, join(entry.parentPath, entry.name)).replaceAll("\\", "/"))
    .sort()
}

test("each channel writes its files under --out, the paths release-channels.yml and the stores expect", (t) => {
  const expected = {
    homebrew: ["surfsense.rb"],
    winget: [
      "manifests/s/SurfSense/SurfSense/2.3.0/SurfSense.SurfSense.installer.yaml",
      "manifests/s/SurfSense/SurfSense/2.3.0/SurfSense.SurfSense.locale.en-US.yaml",
      "manifests/s/SurfSense/SurfSense/2.3.0/SurfSense.SurfSense.yaml",
    ],
    scoop: ["surfsense.json"],
    aur: [".SRCINFO", "PKGBUILD"],
  }
  for (const [channel, files] of Object.entries(expected)) {
    const out = join(scratch(t), "out")
    const run = render(channel, "--version", "2.3.0", "--out", out, "--assets", FIXTURE)
    assert.equal(run.status, 0, run.stderr)
    assert.deepEqual(filesUnder(out), files, channel)
    // Prints what it wrote, so the workflow log shows it.
    for (const file of files) assert.ok(run.stdout.replaceAll("\\", "/").includes(file), `${channel} did not print ${file}`)
    for (const file of files) assert.doesNotMatch(readFileSync(join(out, file), "utf8"), /\r/, file)
  }
})

test("a release whose tag is not --version is refused, and nothing is written", (t) => {
  const out = join(scratch(t), "out")
  const run = render("aur", "--version", "2.3.1", "--out", out, "--assets", FIXTURE)
  assert.notEqual(run.status, 0)
  assert.match(run.stderr, /tagged v2\.3\.0, not v2\.3\.1/)
  assert.deepEqual(filesUnder(out), [])
})

test("a channel whose asset or digest is missing is refused, naming the asset", (t) => {
  const dir = scratch(t)
  const json = JSON.parse(readFileSync(FIXTURE, "utf8"))
  const assets = join(dir, "release.json")

  writeFileSync(assets, JSON.stringify({ ...json, assets: json.assets.filter((a) => a.name !== "SurfSense.AppImage") }))
  let run = render("homebrew", "--version", "2.3.0", "--out", join(dir, "brew"), "--assets", assets)
  assert.notEqual(run.status, 0)
  assert.match(run.stderr, /v2\.3\.0 has no SurfSense\.AppImage/)
  assert.deepEqual(filesUnder(join(dir, "brew")), [])

  const noDigest = json.assets.map((a) => (a.name === "SurfSense-Setup.exe" ? { ...a, digest: null } : a))
  writeFileSync(assets, JSON.stringify({ ...json, assets: noDigest }))
  run = render("scoop", "--version", "2.3.0", "--out", join(dir, "scoop"), "--assets", assets)
  assert.notEqual(run.status, 0)
  assert.match(run.stderr, /SurfSense-Setup\.exe on v2\.3\.0 has no sha256 digest/)
})

test("usage mistakes fail with what was expected", (t) => {
  const out = join(scratch(t), "out")
  for (const [args, message] of [
    [["flathub", "--version", "2.3.0", "--out", out], /homebrew\|winget\|scoop\|aur/],
    [["aur", "--out", out], /--version is required/],
    [["aur", "--version", "2.3.0"], /--out is required/],
    [["aur", "--version", "v2.3.0", "--out", out], /--version must be X\.Y\.Z/],
  ]) {
    const run = render(...args, "--assets", FIXTURE)
    assert.notEqual(run.status, 0, args.join(" "))
    assert.match(run.stderr, message, args.join(" "))
  }
  assert.deepEqual(filesUnder(out), [])
})
