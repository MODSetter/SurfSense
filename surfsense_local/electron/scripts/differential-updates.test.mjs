import assert from "node:assert/strict"
import { readdirSync, readFileSync } from "node:fs"
import test from "node:test"

const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n")

function mainSources(dir = "../src/main/") {
  return readdirSync(new URL(dir, import.meta.url), { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? mainSources(`${dir}${entry.name}/`)
      : /\.ts$/.test(entry.name) && !/\.test\.ts$/.test(entry.name)
        ? [read(`${dir}${entry.name}`)]
        : []
  )
}

// GitHubProvider asks one range per request, which GitHub serves; a Windows
// update then moves about 128 MB instead of the 1.16 GB installer.
test("the app leaves electron-updater's differential downloads on", () => {
  for (const source of mainSources()) {
    assert.doesNotMatch(source, /disableDifferentialDownload/)
  }
})

// A solid 7z saves 72 MB once and makes every Windows update a full download.
test("the Windows installer keeps its per-file payload", () => {
  assert.doesNotMatch(read("../electron-builder.yml"), /differentialPackage:\s*false/)
})
