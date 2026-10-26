import assert from "node:assert/strict"
import { readdirSync, readFileSync } from "node:fs"
import { join, relative } from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"

// The headless entry boots from this folder without Electron (ADR 0072).
const SIDECARS = fileURLToPath(new URL(".", import.meta.url))
const SELF = fileURLToPath(import.meta.url)
const ELECTRON_IMPORT = new RegExp(
  String.raw`(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)["']` + "electron" + String.raw`(?:/[^"']*)?["']`
)

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === "node_modules" ? [] : sourceFiles(path)
    return /\.(?:ts|mts|mjs|js)$/.test(entry.name) && path !== SELF ? [path] : []
  })
}

test("nothing under sidecars/ imports electron", () => {
  const offenders = sourceFiles(SIDECARS)
    .filter((path) => ELECTRON_IMPORT.test(readFileSync(path, "utf8")))
    .map((path) => relative(SIDECARS, path))
  assert.deepEqual(offenders, [])
})
