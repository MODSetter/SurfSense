import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { PINNED_LICENSE, stageLicences } from "./licences.mjs"

const OPENMP = "LLVM OpenMP's licence\n"
const pinned = () => readFileSync(PINNED_LICENSE, "utf8")

/** An unpacked archive holding `files`, and an empty stage beside it. */
function unpacked(t, files) {
  const root = mkdtempSync(join(tmpdir(), "llamacpp-licences-"))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const source = join(root, "unpacked")
  const stage = join(root, "stage")
  mkdirSync(source)
  mkdirSync(stage)
  for (const [name, text] of Object.entries(files)) writeFileSync(join(source, name), text)
  return { source, stage }
}

test("the kept copy is llama.cpp's MIT licence", () => {
  assert.match(pinned(), /^MIT License/)
  assert.match(pinned(), /The ggml authors/)
})

test("a Windows archive gets llama.cpp's licence from the kept copy, and OpenMP's under its own name", (t) => {
  const { source, stage } = unpacked(t, {
    "llama-server.exe": "",
    "libomp.dll": "",
    "LICENSE-LLVM-OpenMP": OPENMP,
  })

  assert.deepEqual(stageLicences(source, stage), ["LICENSE", "LICENSE-LLVM-OpenMP"])
  assert.deepEqual(readdirSync(stage).sort(), ["LICENSE", "LICENSE-LLVM-OpenMP"])
  assert.equal(readFileSync(join(stage, "LICENSE"), "utf8"), pinned())
  assert.equal(readFileSync(join(stage, "LICENSE-LLVM-OpenMP"), "utf8"), OPENMP)
})

test("a macOS or Linux archive's own licence is staged when it matches the kept copy", (t) => {
  const { source, stage } = unpacked(t, { "llama-server": "", LICENSE: pinned().replace(/\r?\n/g, "\r\n") })

  assert.deepEqual(stageLicences(source, stage), ["LICENSE"])
  assert.equal(readFileSync(join(stage, "LICENSE"), "utf8"), pinned().replace(/\r?\n/g, "\r\n"))
})

test("an archive whose licence differs from the kept copy stops the fetch", (t) => {
  const { source, stage } = unpacked(t, {
    "llama-server": "",
    LICENSE: "MIT License\n\nCopyright (c) 2023-2027 The ggml authors\n",
  })

  assert.throws(() => stageLicences(source, stage), /differs from/)
})
