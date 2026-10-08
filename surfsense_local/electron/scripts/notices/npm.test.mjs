import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { npmNotices } from "./npm.mjs"

test("one entry per installed version, with the text of its licence files", () => {
  const root = mkdtempSync(join(tmpdir(), "npm-notices-"))
  try {
    const a = join(root, "a")
    const b = join(root, "b")
    mkdirSync(a)
    mkdirSync(b)
    writeFileSync(join(a, "LICENSE.md"), "MIT License, version one")
    writeFileSync(join(b, "readme.md"), "no licence here")
    // The shape `pnpm licenses list --json` prints: versions and paths pair up.
    const report = {
      MIT: [{ name: "pkg", versions: ["1.0.0", "2.0.0"], paths: [a, b], license: "MIT" }],
    }
    const entries = npmNotices(report, "frontend")
    assert.deepEqual(
      entries.map(({ name, version, tree, license }) => [name, version, tree, license]),
      [
        ["pkg", "1.0.0", "frontend", "MIT"],
        ["pkg", "2.0.0", "frontend", "MIT"],
      ],
    )
    assert.match(entries[0].text, /version one/)
    assert.equal(entries[1].text, "")
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

function withPackage(files, check) {
  const dir = mkdtempSync(join(tmpdir(), "npm-notices-"))
  try {
    for (const [name, text] of Object.entries(files)) writeFileSync(join(dir, name), text)
    check(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

test("a NOTICE file ships as attribution but is not the licence text", () => {
  withPackage({ NOTICE: "Copyright Apache Foo" }, (dir) => {
    const report = { "Apache-2.0": [{ name: "foo", versions: ["1.0.0"], paths: [dir], license: "Apache-2.0" }] }
    const [entry] = npmNotices(report, "frontend")
    assert.equal(entry.text, "")
    assert.equal(entry.notice, "Copyright Apache Foo")
  })
})

const REVIEWED = [
  { tree: "frontend", name: "buffers", version: "0.1.1", license: "MIT", source: "upstream README", text: "MIT text" },
]

test("a reviewed licence text fills in for a package that ships none", () => {
  withPackage({ "README.md": "no licence" }, (dir) => {
    const report = { Unknown: [{ name: "buffers", versions: ["0.1.1"], paths: [dir], license: "Unknown" }] }
    const [entry] = npmNotices(report, "frontend", REVIEWED)
    assert.equal(entry.text, "MIT text")
    assert.equal(entry.license, "MIT")
    assert.match(entry.note, /upstream README/)
  })
})

test("a reviewed text is for its version only, so a bump is reviewed again", () => {
  withPackage({}, (dir) => {
    const report = { Unknown: [{ name: "buffers", versions: ["0.2.0"], paths: [dir], license: "Unknown" }] }
    const [entry] = npmNotices(report, "frontend", REVIEWED)
    assert.equal(entry.text, "")
    assert.equal(entry.license, "Unknown")
  })
})
