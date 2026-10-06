import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { FRAGMENTS } from "./fragments.mjs"
import { mergeNotices, writeNotices } from "./merge.mjs"

const MIT = "MIT License\n\nCopyright (c) someone"

/** Every fragment present and complete; `overrides` replaces whole fragments. */
function fragments(overrides = {}) {
  const all = {
    "npm-frontend": { entries: [{ name: "react", version: "19.0.0", tree: "frontend", license: "MIT", text: MIT }] },
    "npm-electron": { entries: [{ name: "electron-updater", version: "6.8.9", tree: "electron", license: "MIT", text: MIT }] },
    python: { entries: [{ name: "httpx", version: "0.28.1", tree: "python", license: "BSD-3-Clause", text: MIT }] },
    native: { entries: [{ name: "llama.cpp", version: "b11050", tree: "native", license: "MIT", text: MIT }], unstaged: [] },
    models: {
      entries: [{ name: "bge-small-en-v1.5", version: "abc", tree: "model", license: "mit", text: "", note: "no text ships" }],
    },
  }
  return { ...all, ...overrides }
}

const NO_TEXT = { entries: [{ name: "left-pad", version: "1.0.0", tree: "python", license: "MIT", text: "" }] }

test("passes when every dependency carries its licence text", () => {
  const merged = mergeNotices(fragments(), [])
  assert.deepEqual(merged.problems, [])
  assert.equal(merged.entries.length, 5)
})

test("a model pack needs no text: only its licence id is known", () => {
  assert.deepEqual(mergeNotices(fragments(), []).problems, [])
})

test("fails when a Python dependency has no licence text", () => {
  const merged = mergeNotices(fragments({ python: NO_TEXT }), [])
  assert.equal(merged.problems.length, 1)
  assert.match(merged.problems[0], /python left-pad 1\.0\.0 has no licence text/)
})

test("fails when an npm dependency has no licence text", () => {
  const npm = { entries: [{ name: "tiny", version: "2.0.0", tree: "frontend", license: "ISC", text: "  " }] }
  assert.equal(mergeNotices(fragments({ "npm-frontend": npm }), []).problems.length, 1)
})

test("passes when the dependency without text is allowlisted with a reason", () => {
  const allow = [{ tree: "python", name: "left-pad", reason: "upstream ships no licence file; MIT per its metadata" }]
  const merged = mergeNotices(fragments({ python: NO_TEXT }), allow)
  assert.deepEqual(merged.problems, [])
  assert.match(merged.entries.find((e) => e.name === "left-pad").note, /upstream ships no licence file/)
})

test("an allowlist entry without a reason does not count", () => {
  const merged = mergeNotices(fragments({ python: NO_TEXT }), [{ tree: "python", name: "left-pad", reason: "" }])
  assert.equal(merged.problems.length, 1)
})

test("fails when a generator never wrote its fragment", () => {
  const all = fragments()
  delete all.python
  const merged = mergeNotices(all, [])
  assert.match(merged.problems.join("\n"), /no python fragment/)
})

test("every generator has a fragment name", () => {
  assert.deepEqual([...FRAGMENTS].sort(), ["models", "native", "npm-electron", "npm-frontend", "python"])
})

test("writes the merged notices as JSON and as plain text", () => {
  const dir = mkdtempSync(join(tmpdir(), "notices-"))
  try {
    const { entries } = mergeNotices(fragments(), [])
    writeNotices(dir, entries)
    const json = JSON.parse(readFileSync(join(dir, "THIRD_PARTY_NOTICES.json"), "utf8"))
    assert.deepEqual(Object.keys(json.entries[0]).sort(), ["license", "name", "note", "text", "tree", "version"])
    const text = readFileSync(join(dir, "THIRD_PARTY_NOTICES.txt"), "utf8")
    assert.match(text, /llama\.cpp b11050/)
    assert.match(text, /no text ships/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
