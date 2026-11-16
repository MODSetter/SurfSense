import assert from "node:assert/strict"
import test from "node:test"

import { feedManifestProblem } from "./manifest-checks.ts"

const RELEASE = "https://github.com/MODSetter/SurfSense/releases/download/v2.2.4/"

/** stable-linux.yml as our route rewrites it, naming the given release files. */
function linuxManifest(names: string[]) {
  return {
    version: "2.2.4",
    files: names.map((name) => ({ url: `${RELEASE}${name}`, sha512: "c2hhNTEy", size: 1234 })),
    path: `${RELEASE}${names[0]}`,
    sha512: "c2hhNTEy",
  }
}

test("a Linux manifest listing the rpm beside the AppImage and the deb is used", () => {
  const manifest = linuxManifest(["SurfSense.AppImage", "SurfSense.deb", "SurfSense.rpm"])
  assert.equal(feedManifestProblem(manifest), null)
})

// The release also carries the install scripts and checksums; the snap updates through snapd.
for (const name of ["install.sh", "SHA256SUMS", "SurfSense.snap"]) {
  test(`a Linux manifest naming ${name}, which is no installer, is refused`, () => {
    const manifest = linuxManifest(["SurfSense.AppImage", name])
    assert.equal(feedManifestProblem(manifest), "a file outside the GitHub release")
  })
}
