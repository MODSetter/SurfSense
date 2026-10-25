import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { publishedRelease, readReleaseJson } from "./release.mjs"

const FIXTURE = fileURLToPath(new URL("./fixtures/release-v2.3.0.json", import.meta.url))
const fixture = () => JSON.parse(readFileSync(FIXTURE, "utf8"))

/** The fixture with `name`'s asset changed by `change`, or dropped when `change` is null. */
function withAsset(name, change) {
  const json = fixture()
  json.assets = json.assets.flatMap((asset) =>
    asset.name !== name ? [asset] : change === null ? [] : [{ ...asset, ...change }]
  )
  return json
}

test("gives each asset's download URL and the sha256 GitHub keeps for it", () => {
  const release = publishedRelease(fixture(), "2.3.0")

  assert.equal(release.version, "2.3.0")
  assert.equal(release.date, "2026-11-04")
  assert.equal(release.notesUrl, "https://github.com/MODSetter/SurfSense/releases/tag/v2.3.0")
  assert.deepEqual(release.asset("SurfSense.deb"), {
    url: "https://github.com/MODSetter/SurfSense/releases/download/v2.3.0/SurfSense.deb",
    sha256: "5".repeat(64),
  })
  // A blockmap is never taken for the installer it sits beside.
  assert.equal(release.asset("SurfSense-Setup.exe").sha256, "c".repeat(64))
})

test("a release tagged for another version is refused, naming both", () => {
  assert.throws(() => publishedRelease(fixture(), "2.3.1"), /tagged v2\.3\.0, not v2\.3\.1/)
})

test("a draft or a prerelease is refused: no channel may point at one", () => {
  assert.throws(() => publishedRelease({ ...fixture(), draft: true }, "2.3.0"), /v2\.3\.0 is a draft/)
  assert.throws(() => publishedRelease({ ...fixture(), prerelease: true }, "2.3.0"), /v2\.3\.0 is a prerelease/)
})

test("a missing asset is refused when a channel asks for it, naming it", () => {
  const release = publishedRelease(withAsset("SurfSense.deb", null), "2.3.0")
  assert.throws(() => release.asset("SurfSense.deb"), /v2\.3\.0 has no SurfSense\.deb/)
})

test("an asset without a sha256 digest is refused rather than listed unchecked", () => {
  for (const digest of [null, undefined, "", "sha512:" + "5".repeat(128), "sha256:" + "5".repeat(63)]) {
    const release = publishedRelease(withAsset("SurfSense.deb", { digest }), "2.3.0")
    assert.throws(() => release.asset("SurfSense.deb"), /SurfSense\.deb on v2\.3\.0 has no sha256 digest/, String(digest))
  }
})

test("an asset still uploading is refused", () => {
  const release = publishedRelease(withAsset("SurfSense.deb", { state: "starter" }), "2.3.0")
  assert.throws(() => release.asset("SurfSense.deb"), /SurfSense\.deb on v2\.3\.0 is still uploading/)
})

test("an asset served from anywhere but this tag's download path is refused", () => {
  const elsewhere = "https://github.com/someone/SurfSense/releases/download/v2.3.0/SurfSense.deb"
  const release = publishedRelease(withAsset("SurfSense.deb", { browser_download_url: elsewhere }), "2.3.0")
  assert.throws(() => release.asset("SurfSense.deb"), /SurfSense\.deb on v2\.3\.0 is served from .*someone/)
})

test("reads the release from --assets without touching the network", async (t) => {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-channels-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const file = join(dir, "release.json")
  writeFileSync(file, JSON.stringify(fixture()))

  const json = await readReleaseJson({
    version: "2.3.0",
    file,
    fetch: () => assert.fail("fetched with --assets given"),
  })
  assert.equal(json.tag_name, "v2.3.0")
})

test("without --assets, asks GitHub's API for the tag, sending GH_TOKEN only when set", async () => {
  const calls = []
  const fetch = async (url, init) => {
    calls.push({ url, headers: init.headers })
    return new Response(JSON.stringify(fixture()), { status: 200 })
  }

  await readReleaseJson({ version: "2.3.0", env: { GH_TOKEN: "test-token-value" }, fetch })
  await readReleaseJson({ version: "2.3.0", env: {}, fetch })

  assert.equal(calls[0].url, "https://api.github.com/repos/MODSetter/SurfSense/releases/tags/v2.3.0")
  assert.equal(calls[0].headers.Authorization, "Bearer test-token-value")
  assert.equal(calls[1].headers.Authorization, undefined)
})

test("an API error is reported with its status, not parsed as a release", async () => {
  const fetch = async () => new Response('{"message":"Not Found"}', { status: 404, statusText: "Not Found" })
  await assert.rejects(
    readReleaseJson({ version: "9.9.9", env: {}, fetch }),
    /releases\/tags\/v9\.9\.9 answered 404/
  )
})
