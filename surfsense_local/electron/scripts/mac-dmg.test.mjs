import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const ELECTRON = fileURLToPath(new URL("..", import.meta.url))

/** The `dmg:` section of electron-builder.yml. */
function dmgSection() {
  const yml = readFileSync(new URL("../electron-builder.yml", import.meta.url), "utf8").replace(/\r\n/g, "\n")
  return yml.match(/^dmg:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
}

test("the dmg is LZFSE, smaller than zlib and quicker for macOS to verify and copy out of", () => {
  // LZMA (ULMO) and bzip2 (UDBZ) are smaller still but decode several times slower
  // than zlib, which a user waits through when macOS verifies the download.
  assert.match(dmgSection(), /^  format: ULFO$/m)
})

test("electron-builder accepts the whole configuration", async () => {
  // Its schema lists the dmg formats it passes on to hdiutil; ULMO is not among them.
  // Parsed with electron-builder's own YAML reader; its getConfig would log to stdout,
  // which the test runner reads its results from.
  const builder = createRequire(createRequire(import.meta.url).resolve("electron-builder"))
  const appBuilder = createRequire(builder.resolve("app-builder-lib"))
  const { validateConfiguration } = builder("app-builder-lib/out/util/config/config")
  const config = appBuilder("js-yaml").load(readFileSync(join(ELECTRON, "electron-builder.yml"), "utf8"))
  await validateConfiguration(config, { isEnabled: false, add() {} })
})
