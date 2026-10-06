import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { nativeNotices } from "./native.mjs"

const COMPONENTS = [
  { name: "llama.cpp", version: "b1", license: "MIT", folder: "llamacpp", files: ["LICENSE"] },
  { name: "eSpeak NG", version: "1.52.0", license: "GPL-3.0-or-later", folder: "audiocpp", files: ["espeak/COPYING"] },
  { name: "ripgrep", version: "15", license: "Unlicense OR MIT", folder: "opencode", files: ["ripgrep/COPYING", "ripgrep/UNLICENSE"] },
]

function withRoot(build) {
  const root = mkdtempSync(join(tmpdir(), "native-notices-"))
  try {
    build(root)
    return nativeNotices(root, COMPONENTS)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

function put(root, relative, text) {
  const path = join(root, relative)
  mkdirSync(join(path, ".."), { recursive: true })
  writeFileSync(path, text)
}

test("reads the licence files a stage left beside its binary", () => {
  const { entries } = withRoot((root) => {
    put(root, "llamacpp/LICENSE", "MIT License")
    put(root, "audiocpp/espeak/COPYING", "GNU GENERAL PUBLIC LICENSE")
    put(root, "opencode/ripgrep/COPYING", "dual")
    put(root, "opencode/ripgrep/UNLICENSE", "public domain")
  })
  assert.equal(entries.length, 3)
  const ripgrep = entries.find((e) => e.name === "ripgrep")
  assert.equal(ripgrep.tree, "native")
  assert.match(ripgrep.text, /dual/)
  assert.match(ripgrep.text, /public domain/)
})

test("an unstaged folder is reported, not a crash", () => {
  const { entries, unstaged } = withRoot((root) => {
    put(root, "llamacpp/LICENSE", "MIT License")
    mkdirSync(join(root, "audiocpp"))
  })
  assert.deepEqual(entries.map((e) => e.name), ["llama.cpp"])
  assert.deepEqual(unstaged.sort(), ["eSpeak NG", "ripgrep"])
})

test("a staged folder missing its licence yields an entry with no text, for the gate to catch", () => {
  const { entries } = withRoot((root) => {
    put(root, "llamacpp/llama-server", "binary")
  })
  assert.equal(entries[0].text, "")
})
