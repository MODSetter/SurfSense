import assert from "node:assert/strict"
import { createHash, generateKeyPairSync } from "node:crypto"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { createServer } from "node:http"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { signManifest } from "../../src/main/update-feed/manifest-signature.ts"
import { handoverAssetProblems, manifestProblems, updatePath } from "./check-release-manifests.mjs"

const { publicKey, privateKey } = generateKeyPairSync("ed25519")
const KEYS = [Buffer.from(publicKey.export({ format: "jwk" }).x, "base64url").toString("hex")]

const INSTALLERS = {
  "SurfSense-Setup.exe": Buffer.alloc(3000, 1),
  "SurfSense-arm64.zip": Buffer.alloc(2000, 2),
  "SurfSense-arm64.dmg": Buffer.alloc(1000, 3),
  "SurfSense.AppImage": Buffer.alloc(500, 4),
}

const sha512 = (bytes) => createHash("sha512").update(bytes).digest("base64")

/** A manifest as electron-builder writes it for these installers. */
function manifest(version, names) {
  const files = names.map(
    (name) => `  - url: ${name}\n    sha512: ${sha512(INSTALLERS[name])}\n    size: ${INSTALLERS[name].length}\n`
  )
  return `version: ${version}\nfiles:\n${files.join("")}path: ${names[0]}\nsha512: ${sha512(INSTALLERS[names[0]])}\nreleaseDate: '2026-11-25T10:00:00.000Z'\n`
}

const NAMES = { "": ["SurfSense-Setup.exe"], "-mac": ["SurfSense-arm64.zip", "SurfSense-arm64.dmg"], "-linux": ["SurfSense.AppImage"] }

function folder(t) {
  const dir = mkdtempSync(join(tmpdir(), "release-manifests-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

function writeLegacy(dir) {
  for (const name of ["latest.yml", "latest-mac.yml", "latest-linux.yml"]) {
    writeFileSync(join(dir, name), "tag: v0.0.40\nversion: 0.0.40\nfiles:\n  - url: SurfSense-Setup-0.0.40.exe\n")
  }
}

/** 2.4.0's draft: its own stable*.yml, their signed copies as release*.yml, and the legacy bridge's. */
function handoverRelease(t) {
  const dir = folder(t)
  for (const [platform, names] of Object.entries(NAMES)) {
    const stable = Buffer.from(manifest("2.4.0", names))
    writeFileSync(join(dir, `stable${platform}.yml`), stable)
    writeFileSync(join(dir, `release${platform}.yml`), signManifest(stable, `release${platform}.yml`, privateKey))
  }
  writeLegacy(dir)
  return dir
}

/** A later draft: its signed release*.yml, its own stable-linux.yml, 2.4.0's stable files frozen. */
function laterRelease(t, { windows = "2.5.0" } = {}) {
  const dir = folder(t)
  for (const [platform, names] of Object.entries(NAMES)) {
    const own = Buffer.from(manifest(platform === "" ? windows : "2.5.0", names))
    writeFileSync(join(dir, `release${platform}.yml`), signManifest(own, `release${platform}.yml`, privateKey))
    if (platform === "-linux") writeFileSync(join(dir, "stable-linux.yml"), own)
    else writeFileSync(join(dir, `stable${platform}.yml`), `tag: v2.4.0\n${manifest("2.4.0", names)}`)
  }
  writeLegacy(dir)
  return dir
}

const options = (version, extra = {}) => ({ version, handover: "2.4.0", legacy: true, trustedKeys: KEYS, ...extra })

test("the handover release and every one after it take their own path", () => {
  assert.equal(updatePath("2.4.0", "2.4.0"), "handover")
  assert.equal(updatePath("2.4.1", "2.4.0"), "after")
  assert.equal(updatePath("2.10.0", "2.9.0"), "after")
  assert.equal(updatePath("2.3.2", "2.4.0"), "before")
})

test("the handover release's nine manifests pass", (t) => {
  assert.deepEqual(manifestProblems(handoverRelease(t), options("2.4.0")), [])
})

test("a later release's nine manifests pass", (t) => {
  assert.deepEqual(manifestProblems(laterRelease(t), options("2.5.0")), [])
})

test("a missing manifest stops the release, whichever generation reads it", (t) => {
  for (const name of ["release-mac.yml", "stable.yml", "latest-linux.yml"]) {
    const dir = laterRelease(t)
    rmSync(join(dir, name))
    assert.ok(manifestProblems(dir, options("2.5.0")).some((problem) => problem.startsWith(`${name} is missing`)), name)
  }
})

test("an unsigned or altered release*.yml stops the release", (t) => {
  const dir = laterRelease(t)
  writeFileSync(join(dir, "release.yml"), manifest("2.5.0", NAMES[""]))
  writeFileSync(join(dir, "release-mac.yml"), signManifest(Buffer.from(manifest("2.5.0", NAMES["-mac"])), "release-linux.yml", privateKey))

  assert.deepEqual(manifestProblems(dir, options("2.5.0")), [
    "release.yml carries no SurfSense signature",
    "the signature on release-mac.yml does not match",
  ])
})

test("a manifest signed with a key the app does not trust stops the release", (t) => {
  const other = generateKeyPairSync("ed25519").publicKey.export({ format: "jwk" }).x
  const trustedKeys = [Buffer.from(other, "base64url").toString("hex")]

  assert.deepEqual(manifestProblems(laterRelease(t), options("2.5.0", { trustedKeys })), [
    "the signature on release.yml does not match",
    "the signature on release-mac.yml does not match",
    "the signature on release-linux.yml does not match",
  ])
})

test("on the handover release the signed copies must be the stable files byte for byte", (t) => {
  const dir = handoverRelease(t)
  writeFileSync(join(dir, "stable-mac.yml"), manifest("2.4.0", ["SurfSense-arm64.zip"]))

  assert.deepEqual(manifestProblems(dir, options("2.4.0")), ["release-mac.yml is not stable-mac.yml signed"])
})

test("a frozen stable file must send older apps to the handover release", (t) => {
  const dir = laterRelease(t)
  writeFileSync(join(dir, "stable.yml"), manifest("2.4.0", NAMES[""]))
  writeFileSync(join(dir, "stable-mac.yml"), `tag: v2.4.0\n${manifest("2.5.0", NAMES["-mac"])}`)

  assert.deepEqual(manifestProblems(dir, options("2.5.0")), [
    'stable.yml does not start with "tag: v2.4.0"',
    "stable-mac.yml does not name the handover release 2.4.0",
  ])
})

test("stable-linux.yml is the release's own, since Linux checks no signature", (t) => {
  const dir = laterRelease(t)
  writeFileSync(join(dir, "stable-linux.yml"), `tag: v2.4.0\n${manifest("2.4.0", NAMES["-linux"])}`)

  assert.deepEqual(manifestProblems(dir, options("2.5.0")), ["stable-linux.yml is not this release's own release-linux.yml"])
})

test("a release with no signed Windows build carries the last signed one's release.yml, and only then", (t) => {
  assert.deepEqual(manifestProblems(laterRelease(t, { windows: "2.4.0" }), options("2.5.0", { windowsCarried: true })), [])
  assert.deepEqual(manifestProblems(laterRelease(t, { windows: "2.4.0" }), options("2.5.0")), ["release.yml names 2.4.0, not 2.5.0"])
  assert.deepEqual(manifestProblems(laterRelease(t), options("2.5.0", { windowsCarried: true })), [
    "release.yml carried forward names 2.5.0, not an earlier signed Windows build",
  ])
  assert.ok(
    manifestProblems(handoverRelease(t), options("2.4.0", { windowsCarried: true })).includes(
      "the handover release must carry its own signed Windows build"
    )
  )
})

test("legacy manifests that do not point at v0.0.40 stop the release", (t) => {
  const dir = laterRelease(t)
  writeFileSync(join(dir, "latest.yml"), "version: 2.5.0\n")

  assert.deepEqual(manifestProblems(dir, options("2.5.0")), ["latest.yml does not send legacy apps to v0.0.40"])
})

test("the frozen files' sha512 and size are checked against the handover release's own installers", async (t) => {
  const served = { ...INSTALLERS }
  const server = createServer((request, response) => {
    const name = decodeURIComponent(request.url.split("/").pop())
    if (!served[name]) return response.writeHead(404).end()
    response.writeHead(200, { "content-length": served[name].length }).end(served[name])
  })
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve))
  t.after(() => server.close())
  const releaseDownload = (version) => `http://127.0.0.1:${server.address().port}/download/v${version}/`
  const dir = laterRelease(t)

  assert.deepEqual(await handoverAssetProblems(dir, "2.4.0", { releaseDownload }), [])

  // Someone re-uploaded 2.4.0's zip: every Mac app before 2.4.0 would refuse it.
  served["SurfSense-arm64.zip"] = Buffer.alloc(2000, 9)
  delete served["SurfSense-Setup.exe"]
  const base = releaseDownload("2.4.0")
  assert.deepEqual(await handoverAssetProblems(dir, "2.4.0", { releaseDownload }), [
    `${base}SurfSense-Setup.exe could not be read (HTTP 404)`,
    `${base}SurfSense-arm64.zip is not the file stable-mac.yml names: its sha512 or size changed`,
  ])
})
