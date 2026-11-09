import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { homebrewCask } from "./homebrew.mjs"
import { publishedRelease } from "./release.mjs"

const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))
const release = publishedRelease(JSON.parse(readFileSync(FIXTURE, "utf8")), "2.3.0")
const cask = homebrewCask(release)["surfsense.rb"]

/** The lines of the `on_<os>` block, without the block's own do/end. */
function block(os) {
  const match = cask.match(new RegExp(`^  on_${os} do\\n([\\s\\S]*?)^  end\\n`, "m"))
  assert.ok(match, `no on_${os} block`)
  return match[1]
}

test("names the arm64 dmg and the x86_64 AppImage by this release's digests", () => {
  assert.match(cask, /^cask "surfsense" do$/m)
  assert.match(cask, /^  version "2\.3\.0"$/m)
  assert.match(cask, /^  os macos: "-arm64\.dmg", linux: "\.AppImage"$/m)
  assert.match(cask, new RegExp(`^  sha256 arm: {10}"${"1".repeat(64)}",\\n {9}x86_64_linux: "${"4".repeat(64)}"$`, "m"))
  assert.match(
    cask,
    /^  url "https:\/\/github\.com\/MODSetter\/SurfSense\/releases\/download\/v#\{version\}\/SurfSense#\{os\}"$/m
  )
})

test("top-level stanzas follow Homebrew's order, which brew style enforces", () => {
  const stanzas = [...cask.matchAll(/^  ([a-z0-9_]+)\b/gm)]
    .map((match) => match[1])
    .filter((name) => name !== "end")
  assert.deepEqual(stanzas, [
    "os",
    "version",
    "sha256",
    "on_macos",
    "on_linux",
    "url",
    "name",
    "desc",
    "homepage",
    "livecheck",
  ])
  // brew style wants one blank line between stanza groups and none inside one.
  assert.match(cask, /\n  end\n  on_linux do\n/)
  assert.match(cask, /x86_64_linux: "[0-9a-f]{64}"\n\n  on_macos do\n/)
})

test("auto_updates is declared for the Mac app only, so plain brew upgrade still updates Linux", () => {
  // On macOS brew upgrades it anyway while the app bundle is older than the cask; an AppImage has no bundle to read.
  assert.match(block("macos"), /^    auto_updates true\n    depends_on arch: :arm64\n    depends_on macos: :ventura\n\n    app "SurfSense\.app"\n/)
  assert.doesNotMatch(block("linux"), /auto_updates/)
  assert.doesNotMatch(cask, /^  auto_updates/m)
  assert.match(block("linux"), /^    depends_on arch: :x86_64\n\n    app_image "SurfSense\.AppImage"\n/)
})

test("zap trashes the app's data folders and never the legacy app's", () => {
  const mac = block("macos")
  const linux = block("linux")
  for (const path of [
    "~/.surfsense",
    "~/Library/Caches/com.surfsense.app",
    "~/Library/Caches/surfsense-local-electron-updater",
    "~/Library/Preferences/com.surfsense.app.plist",
  ]) {
    assert.ok(mac.includes(`"${path}",`), path)
  }
  for (const path of ["~/.surfsense", "~/.cache/surfsense-local-electron-updater"]) {
    assert.ok(linux.includes(`"${path}",`), path)
  }
  // The 0.0.x desktop kept its data there; 2.x moved it to ~/.surfsense.
  assert.doesNotMatch(cask, /Application Support\/SurfSense/)
  // Each zap list is in Homebrew's alphabetical order.
  for (const os of ["macos", "linux"]) {
    const paths = [...block(os).matchAll(/^      "(.+)",$/gm)].map((match) => match[1])
    assert.deepEqual(paths, [...paths].sort(), os)
  }
})

test("desc passes Homebrew's description rules", () => {
  const desc = cask.match(/^  desc "(.+)"$/m)[1]
  assert.ok(desc.length <= 80)
  assert.match(desc, /^[A-Z]/)
  assert.doesNotMatch(desc, /^(the|an?)\s/i)
  assert.doesNotMatch(desc, /^SurfSense\b/i)
  assert.doesNotMatch(desc, /\.$|\b(mac ?os|you|your|alternative)\b/i)
})

test("homepage has the slash after the domain that brew style requires", () => {
  assert.match(cask, /^  homepage "https:\/\/www\.surfsense\.com\/"$/m)
})

test("livecheck reads GitHub's latest release, since tags are pushed before the release is published", () => {
  assert.match(cask, /^  livecheck do\n    url :url\n    strategy :github_latest\n  end\n/m)
})

const ruby = spawnSync("ruby", ["--version"], { encoding: "utf8", timeout: 20_000 }).status === 0

test("is valid Ruby", { skip: !ruby && "needs ruby" }, (t) => {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-cask-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const file = join(dir, "surfsense.rb")
  writeFileSync(file, cask)
  const check = spawnSync("ruby", ["-c", file], { encoding: "utf8", timeout: 20_000 })
  assert.equal(check.status, 0, check.stderr)
})
