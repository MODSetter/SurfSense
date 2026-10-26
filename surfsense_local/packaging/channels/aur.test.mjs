import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readlinkSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { aurPackage } from "./aur.mjs"
import { publishedRelease } from "./release.mjs"

const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))
const THIS_FILE = fileURLToPath(import.meta.url).replaceAll("\\", "/")
const release = publishedRelease(JSON.parse(readFileSync(FIXTURE, "utf8")), "2.3.0")
const { PKGBUILD: pkgbuild, ".SRCINFO": srcinfo } = aurPackage(release)

/** A bash that runs and can read this checkout: on Windows `bash` may be WSL's. */
const bash =
  spawnSync("bash", ["-c", 'test -r "$1" && echo ok', "probe", THIS_FILE], { encoding: "utf8", timeout: 20_000 })
    .stdout?.trim() === "ok"

/** Runs `script` in bash with the rendered PKGBUILD's path as $1 and `args` after it. */
function withPkgbuild(t, script, ...args) {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-aur-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const file = join(dir, "PKGBUILD")
  writeFileSync(file, pkgbuild)
  const run = spawnSync("bash", ["-c", script, "bash", file.replaceAll("\\", "/"), ...args], {
    encoding: "utf8",
    timeout: 60_000,
  })
  assert.equal(run.status, 0, run.stderr)
  return run.stdout
}

test("repackages this tag's deb, checked by GitHub's digest", () => {
  assert.match(pkgbuild, /^pkgname=surfsense-bin$/m)
  assert.match(pkgbuild, /^pkgver=2\.3\.0$/m)
  assert.match(pkgbuild, /^pkgrel=1$/m)
  assert.match(pkgbuild, /^arch=\('x86_64'\)$/m)
  assert.match(pkgbuild, /^license=\('Apache-2\.0'\)$/m)
  assert.match(
    pkgbuild,
    /^source=\("\$\{pkgname\}-\$\{pkgver\}\.deb::https:\/\/github\.com\/MODSetter\/SurfSense\/releases\/download\/v\$\{pkgver\}\/SurfSense\.deb"\)$/m
  )
  assert.match(pkgbuild, new RegExp(`^sha256sums=\\('${"5".repeat(64)}'\\)$`, "m"))
  // Stripping would break the frozen Python backend and the prebuilt model runtimes.
  assert.match(pkgbuild, /^options=\('!strip' '!debug'\)$/m)
})

test("depends on the Arch packages behind every Depends of the deb", () => {
  const depends = pkgbuild.match(/^depends=\(\n([\s\S]*?)^\)$/m)[1].match(/'([^']+)'/g).map((name) => name.slice(1, -1))
  // electron-builder's deb defaults, libgomp1 for llama.cpp (electron-builder.yml), and ALSA, which Electron links.
  const archNames = {
    "libgtk-3-0": "gtk3",
    libnotify4: "libnotify",
    libnss3: "nss",
    libxss1: "libxss",
    libxtst6: "libxtst",
    "xdg-utils": "xdg-utils",
    "libatspi2.0-0": "at-spi2-core",
    libuuid1: "util-linux-libs",
    "libsecret-1-0": "libsecret",
    libgomp1: "gcc-libs",
    libasound2: "alsa-lib",
  }
  assert.deepEqual(depends, Object.values(archNames).sort())
  assert.match(pkgbuild, /^  'libappindicator: /m)
  assert.match(pkgbuild, /^  'vulkan-icd-loader: /m)
})

test("is valid bash", { skip: !bash && "needs bash" }, (t) => {
  withPkgbuild(t, 'bash -n "$1"')
})

test(".SRCINFO says what makepkg --printsrcinfo reads from the PKGBUILD", { skip: !bash && "needs bash" }, (t) => {
  // makepkg's own order: pkgbase, its single values, its arrays, then each pkgname.
  const printed = withPkgbuild(
    t,
    `source "$1"
     printf 'pkgbase = %s\\n' "$pkgname"
     for name in pkgdesc pkgver pkgrel url; do printf '\\t%s = %s\\n' "$name" "\${!name}"; done
     for name in arch license depends optdepends provides conflicts options source sha256sums; do
       eval "values=(\\"\\\${$name[@]}\\")"
       for value in "\${values[@]}"; do printf '\\t%s = %s\\n' "$name" "$value"; done
     done
     printf '\\npkgname = %s\\n' "$pkgname"`
  )
  assert.equal(srcinfo, printed)
  assert.match(srcinfo, /^\tsource = surfsense-bin-2\.3\.0\.deb::https:\/\/github\.com\/MODSetter\/SurfSense\/releases\/download\/v2\.3\.0\/SurfSense\.deb$/m)
})

test(
  "package() installs the deb's files marked as the AUR's, without electron-updater's feed",
  // makepkg runs on Linux; MSYS's ln copies rather than links, so Windows cannot run it.
  { skip: process.platform === "win32" ? "makepkg runs on Linux" : !bash && "needs bash" },
  (t) => {
    const work = mkdtempSync(join(tmpdir(), "surfsense-aur-pkg-"))
    t.after(() => rmSync(work, { recursive: true, force: true }))
    const srcdir = join(work, "src")
    const pkgdir = join(work, "pkg")
    const deb = join(work, "deb")
    const files = {
      "opt/SurfSense/surfsense-local": "",
      "opt/SurfSense/resources/app-update.yml": "provider: github\n",
      "opt/SurfSense/resources/package-type": "deb\n",
      "opt/SurfSense/resources/licenses/THIRD_PARTY_NOTICES.txt": "notices\n",
      "usr/share/applications/surfsense-local.desktop": "[Desktop Entry]\n",
      "usr/share/icons/hicolor/512x512/apps/surfsense-local.png": "",
    }
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(deb, path)), { recursive: true })
      writeFileSync(join(deb, path), content)
    }
    mkdirSync(srcdir)
    mkdirSync(pkgdir)
    // As makepkg leaves a deb's ar archive: data.tar.* in $srcdir, paths starting ./
    const tar = spawnSync("tar", ["-czf", join(srcdir, "data.tar.gz"), "-C", deb, "."], { timeout: 60_000 })
    assert.equal(tar.status, 0, String(tar.stderr))

    withPkgbuild(
      t,
      `set -e
       source "$1"
       srcdir=$2 pkgdir=$3
       command -v bsdtar >/dev/null || bsdtar() { tar "$@"; }
       package`,
      srcdir,
      pkgdir
    )

    const resources = join(pkgdir, "opt/SurfSense/resources")
    assert.equal(readFileSync(join(resources, "install-channel"), "utf8"), "aur\n")
    assert.ok(!existsSync(join(resources, "app-update.yml")))
    assert.ok(!existsSync(join(resources, "package-type")))
    assert.equal(readlinkSync(join(pkgdir, "usr/bin/surfsense-local")), "/opt/SurfSense/surfsense-local")
    assert.equal(readlinkSync(join(pkgdir, "usr/bin/surfsense")), "/opt/SurfSense/surfsense-local")
    assert.equal(
      readlinkSync(join(pkgdir, "usr/share/licenses/surfsense-bin/THIRD_PARTY_NOTICES.txt")),
      "/opt/SurfSense/resources/licenses/THIRD_PARTY_NOTICES.txt"
    )
    assert.ok(existsSync(join(pkgdir, "usr/share/applications/surfsense-local.desktop")))
    assert.ok(existsSync(join(pkgdir, "usr/share/icons/hicolor/512x512/apps/surfsense-local.png")))
  }
)
