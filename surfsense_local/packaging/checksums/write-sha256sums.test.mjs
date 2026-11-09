import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { findDraft, sha256sums } from "./write-sha256sums.mjs"

const SCRIPT = fileURLToPath(new URL("./write-sha256sums.mjs", import.meta.url))
const FIXTURE = fileURLToPath(new URL("./fixtures/releases.json", import.meta.url))
const RELEASES = JSON.parse(readFileSync(FIXTURE, "utf8"))

test("writes the draft's assets in sha256sum format, sorted by name, without SHA256SUMS itself", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-sha256sums-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const out = join(dir, "SHA256SUMS")

  execFileSync(process.execPath, [SCRIPT, "--releases", FIXTURE, "--tag", "v2.3.0", "--out", out])

  assert.equal(
    readFileSync(out, "utf8"),
    [
      "8888888888888888888888888888888888888888888888888888888888888888  InRelease",
      "7777777777777777777777777777777777777777777777777777777777777777  SurfSense-Setup.exe",
      "5555555555555555555555555555555555555555555555555555555555555555  SurfSense-arm64.dmg.blockmap",
      "2222222222222222222222222222222222222222222222222222222222222222  SurfSense.deb",
      "6666666666666666666666666666666666666666666666666666666666666666  install.sh",
      "9999999999999999999999999999999999999999999999999999999999999999  latest.yml",
      "1111111111111111111111111111111111111111111111111111111111111111  stable-linux.yml",
      "4444444444444444444444444444444444444444444444444444444444444444  surfsense-archive-keyring.gpg",
      "",
    ].join("\n")
  )
})

test("a published release is never taken for the draft", () => {
  assert.throws(() => findDraft(RELEASES, "v2.2.3"), /no draft release is tagged v2\.2\.3/)
})

test("two drafts on one tag fail rather than guess which one the build filled", () => {
  const stray = { tag_name: "v2.3.0", draft: true, prerelease: false, assets: [] }
  assert.throws(() => findDraft([...RELEASES, [stray]], "v2.3.0"), /2 draft releases are tagged v2\.3\.0/)
})

test("an asset GitHub has no sha256 digest for fails, naming it, so no file goes unlisted", () => {
  const release = {
    tag_name: "v2.3.0",
    draft: true,
    assets: [
      { name: "SurfSense.deb", digest: `sha256:${"2".repeat(64)}` },
      { name: "SurfSense.rpm", digest: null },
    ],
  }
  assert.throws(() => sha256sums(release), /SurfSense\.rpm/)
})

test("a draft with nothing to list fails rather than write an empty SHA256SUMS", () => {
  const release = { tag_name: "v2.3.0", draft: true, assets: [{ name: "SHA256SUMS", digest: `sha256:${"3".repeat(64)}` }] }
  assert.throws(() => sha256sums(release), /no assets/)
})
