import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { licenceFiles } from "./licence-files.mjs"

function inDir(names) {
  const dir = mkdtempSync(join(tmpdir(), "licence-files-"))
  for (const name of names) writeFileSync(join(dir, name), `text of ${name}`)
  return dir
}

test("takes every licence and copying file, in either spelling", () => {
  const dir = inDir(["LICENSE-MIT", "licence.txt", "COPYING", "UNLICENSE", "README.md", "license-checker.js"])
  try {
    const { text } = licenceFiles(dir)
    for (const name of ["LICENSE-MIT", "licence.txt", "COPYING", "UNLICENSE"]) assert.match(text, new RegExp(`text of ${name}`))
    assert.doesNotMatch(text, /README|license-checker/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("a NOTICE file is attribution, kept apart from the licence text", () => {
  const dir = inDir(["LICENSE", "NOTICE.txt"])
  try {
    const { text, notice } = licenceFiles(dir)
    assert.equal(text, "text of LICENSE")
    assert.equal(notice, "text of NOTICE.txt")
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("a NOTICE file alone is no licence text", () => {
  const dir = inDir(["NOTICE"])
  try {
    assert.deepEqual(licenceFiles(dir), { text: "", notice: "text of NOTICE" })
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test("a folder that is not there has no text", () => {
  assert.deepEqual(licenceFiles(join(tmpdir(), "does-not-exist-notices")), { text: "", notice: "" })
})
