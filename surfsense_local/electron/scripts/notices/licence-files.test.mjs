import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { licenceText } from "./licence-files.mjs"

test("takes every licence, copying and notice file, in either spelling", () => {
  const dir = mkdtempSync(join(tmpdir(), "licence-files-"))
  try {
    for (const name of ["LICENSE-MIT", "licence.txt", "COPYING", "NOTICE", "README.md", "license-checker.js"]) {
      writeFileSync(join(dir, name), `text of ${name}`)
    }
    const text = licenceText(dir)
    for (const name of ["LICENSE-MIT", "licence.txt", "COPYING", "NOTICE"]) assert.match(text, new RegExp(`text of ${name}`))
    assert.doesNotMatch(text, /README|license-checker/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("a folder that is not there has no text", () => {
  assert.equal(licenceText(join(tmpdir(), "does-not-exist-notices")), "")
})
