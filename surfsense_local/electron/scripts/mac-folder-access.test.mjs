import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

const builder = readFileSync(new URL("../electron-builder.yml", import.meta.url), "utf8")

// Without its sentence macOS refuses the access and shows no prompt, so a moved
// folder would simply vanish. Only a signed build shows this, so it is held here.
for (const key of [
  "NSRemovableVolumesUsageDescription",
  "NSNetworkVolumesUsageDescription",
  "NSDesktopFolderUsageDescription",
  "NSDocumentsFolderUsageDescription",
  "NSDownloadsFolderUsageDescription",
]) {
  test(`the mac build says why it needs ${key}`, () => {
    assert.match(builder, new RegExp(`^    ${key}: ".+"$`, "m"))
  })
}
