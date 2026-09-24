import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { exe } from "./platform.ts"
import { sdcppSpec } from "./sdcpp.ts"
import type { SidecarContext } from "./types.ts"

const runtime = { file: "sdxl-turbo.gguf", args: [] }

function staged(): SidecarContext {
  const root = mkdtempSync(join(tmpdir(), "sdcpp-"))
  const binaries = join(root, "sdcpp")
  const images = join(root, "images")
  mkdirSync(binaries, { recursive: true })
  mkdirSync(images, { recursive: true })
  writeFileSync(join(binaries, exe("sd-server")), "")
  writeFileSync(join(images, runtime.file), "")
  return {
    packaged: true,
    backendDir: root,
    binariesDir: root,
    host: "127.0.0.1",
    apiPort: 1,
    dataDir: root,
    secret: "s",
    imagePort: 9998,
    imageModelsDir: images,
    imageUrl: "http://127.0.0.1:9998",
    sdcppBinariesDir: binaries,
  }
}

test("runs in dev too, because only the binary's path differs", () => {
  assert.ok(sdcppSpec({ ...staged(), packaged: false }, runtime))
})

test("does not run when the pinned build is not staged", () => {
  const ctx = staged()
  assert.equal(
    sdcppSpec({ ...ctx, sdcppBinariesDir: join(ctx.dataDir, "absent") }, runtime),
    null
  )
})

test("does not run before a model is chosen", () => {
  assert.equal(sdcppSpec(staged(), { file: null, args: [] }), null)
})

test("runs from the staged directory so sd-server finds its ggml backends", () => {
  const ctx = staged()
  const spec = sdcppSpec(ctx, runtime)
  assert.ok(spec)
  assert.equal(spec.cwd, ctx.sdcppBinariesDir)
})
