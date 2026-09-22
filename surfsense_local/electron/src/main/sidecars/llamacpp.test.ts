import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { llamacppSpec, PRESET_FILE } from "./llamacpp.ts"
import { exe } from "./platform.ts"
import type { SidecarContext } from "./types.ts"

function staged(): { ctx: SidecarContext; models: string } {
  const root = mkdtempSync(join(tmpdir(), "llamacpp-"))
  const binaries = join(root, "resources")
  const runtime = join(binaries, "llamacpp")
  const models = join(root, "models")
  mkdirSync(runtime, { recursive: true })
  mkdirSync(models, { recursive: true })
  writeFileSync(join(runtime, exe("llama-server")), "")
  return {
    ctx: {
      packaged: true,
      backendDir: root,
      binariesDir: binaries,
      host: "127.0.0.1",
      apiPort: 1,
      dataDir: root,
      secret: "s",
      llamacppPort: 9999,
      llamacppModelsDir: models,
      llamacppBinariesDir: runtime,
    },
    models,
  }
}

test("runs in dev too, because only the binary's path differs", () => {
  // The previous runtime was a system daemon a developer already had running,
  // so dev needed no wiring. A pinned build has to be started by the app in
  // both modes, or dev tests a version the app never ships.
  const { ctx } = staged()
  assert.ok(llamacppSpec({ ...ctx, packaged: false }))
})

test("does not run when the pinned build is not staged", () => {
  const { ctx } = staged()
  assert.equal(
    llamacppSpec({ ...ctx, llamacppBinariesDir: join(ctx.binariesDir, "absent") }),
    null
  )
})

test("runs from the library directory so ggml can find its backends", () => {
  // ggml scans the running executable's own directory. Anywhere else it reports
  // no devices, silently, and every model lands on the CPU.
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.cwd, ctx.llamacppBinariesDir)
})

test("starts with no model, because the router serves an empty directory", () => {
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.ok(!spec.args.includes("--models-preset"))
  assert.ok(spec.args.includes("--models-dir"))
})

test("passes the preset file once the API has written one", () => {
  const { ctx, models } = staged()
  writeFileSync(join(models, PRESET_FILE), "[m]\nctx-size = 16384\n")

  const spec = llamacppSpec(ctx)

  assert.ok(spec)
  assert.ok(spec.args.includes("--models-preset"))
  assert.equal(spec.args.at(-1), join(models, PRESET_FILE))
})

test("keeps a loaded model resident between two questions", () => {
  // Measured: without this a model self-evicted after roughly 30s idle, which
  // turns the second question of a conversation into a reload.
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.args[spec.args.indexOf("--sleep-idle-seconds") + 1], "300")
})

test("never sets a layer count, which would abort --fit", () => {
  // With -ngl set by hand the fitter aborts and the model loads entirely on the
  // CPU: no error, exit 0, and it looks like it worked.
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.ok(!spec.args.some((a) => a === "-ngl" || a === "--n-gpu-layers"))
})

test("keeps llama.cpp's cache inside the app data dir", () => {
  const { ctx, models } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.env.LLAMA_CACHE, models)
})

test("never sets a router wide reasoning budget", () => {
  // Two reasons, and the second is the one that bites. A budget here applies to
  // every answer, not just the short calls that need it. And the server only
  // reads the per request `thinking_budget_tokens` while this flag sits at its
  // default, so passing it would silently undo the fix that keeps a thinking
  // model from returning an empty title.
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)
  assert.ok(spec)
  assert.ok(!spec.args.some((arg) => arg.startsWith("--reasoning-budget")))
})

test("the router is told to load models on demand, rather than relying on its default", () => {
  // The chat path no longer asks the router to load anything: the proxy calls
  // ensure_model_ready before forwarding, so a cold model loads on the request
  // that needs it. Asking as well was a check-then-act across a socket and lost
  // the race to the request already loading the model, which took out title
  // generation with a 400 `model is already running`.
  //
  // That correctness now rests on an upstream default. Stating it means the day
  // it flips we get a clear failure here rather than a silent one in a chat.
  const { ctx } = staged()
  const spec = llamacppSpec(ctx)

  assert.ok(spec)
  assert.ok(spec.args.includes("--models-autoload"))
})
