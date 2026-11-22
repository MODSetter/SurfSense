import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { publisherNameProblem } from "./check-publisher-name.mjs"

// app-update.yml as electron-builder writes it into resources/ on Windows.
const WRITTEN = `owner: MODSetter
repo: SurfSense
provider: github
channel: release
publisherName:
  - SurfSense
updaterCacheDirName: surfsense-local-electron-updater
`

test("an app-update.yml that names its publisher passes", () => {
  assert.equal(publisherNameProblem(WRITTEN), null)
})

test("one that names none, or an empty one, fails, since updates would then skip the check", () => {
  assert.match(publisherNameProblem(WRITTEN.replace("publisherName:\n  - SurfSense\n", "")), /names no publisher/)
  assert.match(publisherNameProblem(WRITTEN.replace("  - SurfSense\n", "")), /names no publisher/)
  assert.match(publisherNameProblem(WRITTEN.replace("  - SurfSense", "  - ''")), /empty publisher/)
})

test("electron-builder writes the name from its publish config, whatever signs the build", () => {
  // Left to the signer it would be Azure's alone, and a later certificate might write none.
  const yml = readFileSync(new URL("../../electron-builder.yml", import.meta.url), "utf8").replace(/\r\n/g, "\n")
  const publish = yml.match(/^publish:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  assert.match(publish, /^  publisherName:\n    - SurfSense$/m)
})
