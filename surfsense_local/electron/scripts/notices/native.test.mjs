import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { DICTIONARIES_FOR } from "../../../runtimes/audiocpp/espeak/dictionaries.mjs"
import { NATIVE_COMPONENTS } from "./native-components.mjs"
import { nativeNotices } from "./native.mjs"

const COMPONENTS = [
  { name: "llama.cpp", version: "b1", license: "MIT", folder: "llamacpp", files: ["LICENSE"] },
  { name: "eSpeak NG", version: "1.52.0", license: "GPL-3.0-or-later", folder: "audiocpp", files: ["espeak/COPYING"] },
  { name: "ripgrep", version: "15", license: "Unlicense OR MIT", folder: "opencode", files: ["ripgrep/COPYING", "ripgrep/LICENSE-MIT", "ripgrep/UNLICENSE"] },
]

function withRoot(build, components = COMPONENTS, platform = "linux") {
  const root = mkdtempSync(join(tmpdir(), "native-notices-"))
  try {
    build(root)
    return nativeNotices(root, components, platform)
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
    put(root, "opencode/ripgrep/LICENSE-MIT", "MIT terms")
    put(root, "opencode/ripgrep/UNLICENSE", "public domain")
  })
  assert.equal(entries.length, 3)
  const ripgrep = entries.find((e) => e.name === "ripgrep")
  assert.equal(ripgrep.tree, "native")
  assert.match(ripgrep.text, /dual/)
  assert.match(ripgrep.text, /MIT terms/)
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

test("a staged folder missing a listed licence file fails, naming it", () => {
  assert.throws(
    () =>
      withRoot((root) => {
        put(root, "llamacpp/LICENSE", "MIT License")
        put(root, "opencode/ripgrep/COPYING", "dual")
        put(root, "opencode/ripgrep/UNLICENSE", "public domain")
      }),
    /ripgrep.*opencode[/\\]ripgrep[/\\]LICENSE-MIT/s,
  )
})

test("a listed licence file holding only whitespace fails too", () => {
  assert.throws(
    () =>
      withRoot((root) => {
        put(root, "llamacpp/LICENSE", "  \n")
      }),
    /llama\.cpp.*LICENSE/s,
  )
})

const OPENMP = { name: "LLVM OpenMP", version: "b1", license: "Apache-2.0 WITH LLVM-exception", folder: "llamacpp",
  files: ["LICENSE-LLVM-OpenMP"], platforms: ["win32"] }

test("a component for another platform is neither read nor reported", () => {
  const { entries, unstaged } = withRoot((root) => put(root, "llamacpp/LICENSE", "MIT License"), [COMPONENTS[0], OPENMP], "linux")
  assert.deepEqual(entries.map((e) => e.name), ["llama.cpp"])
  assert.deepEqual(unstaged, [])
})

test("on its platform, a component's licence file is required", () => {
  const build = (root) => put(root, "llamacpp/LICENSE", "MIT License")
  assert.throws(() => withRoot(build, [COMPONENTS[0], OPENMP], "win32"), /LLVM OpenMP.*LICENSE-LLVM-OpenMP/s)
  const { entries } = withRoot((root) => {
    build(root)
    put(root, "llamacpp/LICENSE-LLVM-OpenMP", "LLVM OpenMP's licence")
  }, [COMPONENTS[0], OPENMP], "win32")
  assert.deepEqual(entries.map((e) => e.name), ["llama.cpp", "LLVM OpenMP"])
  assert.equal(entries[1].platforms, undefined)
})

test("eSpeak NG's notice says when it was modified, which dictionaries ship and where its full source is", () => {
  // GPL-3.0 section 5(a): a modified copy says so and gives a relevant date.
  const espeak = NATIVE_COMPONENTS.find((c) => c.name === "eSpeak NG")
  assert.match(espeak.note, new RegExp(`modified this copy on ${DICTIONARIES_FOR.on}`))
  assert.match(espeak.note, /trimm/)
  assert.match(espeak.note, /\bru, si, ta, te\b/)
  assert.match(espeak.note, new RegExp(`github\\.com/espeak-ng/espeak-ng/tree/${espeak.version.replaceAll(".", "\\.")}`))
})

test("Windows carries OpenMP's licence beside llama.cpp, for its libomp.dll", () => {
  const openmp = NATIVE_COMPONENTS.find((c) => c.files.includes("LICENSE-LLVM-OpenMP"))
  assert.equal(openmp?.folder, "llamacpp")
  assert.deepEqual(openmp.platforms, ["win32"])
})
