import assert from "node:assert/strict"
import test from "node:test"

import { githubManifestProblem, mirrorManifestProblem } from "./manifest-checks.ts"

/** release-linux.yml as electron-builder writes it, naming the given release files. */
function linuxManifest(names: string[], version = "2.5.0") {
  return {
    version,
    files: names.map((name) => ({ url: name, sha512: "c2hhNTEy", size: 1234 })),
    path: names[0],
    sha512: "c2hhNTEy",
  }
}

test("a Linux manifest listing the rpm beside the AppImage and the deb is used", () => {
  const manifest = linuxManifest(["SurfSense.AppImage", "SurfSense.deb", "SurfSense.rpm"])
  assert.equal(githubManifestProblem(manifest), null)
  assert.equal(mirrorManifestProblem(manifest, "https://updates.corp.example/surfsense/"), null)
})

test("a manifest with no files, or no release version, is refused", () => {
  assert.equal(githubManifestProblem(linuxManifest([])), "no files")
  assert.equal(githubManifestProblem(linuxManifest(["SurfSense.deb"], "2.5.0-rc.1")), "no release version")
})
