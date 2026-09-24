import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs"
import { availableParallelism, tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { audiocppSpec, audioThreads, SERVER_CONFIG } from "./audiocpp.ts"
import { exe } from "./platform.ts"
import type { SidecarContext } from "./types.ts"

/** A staged build and an audio folder, with the API's config written or not. */
function staged({ config = true } = {}): { ctx: SidecarContext; audio: string } {
  const root = mkdtempSync(join(tmpdir(), "audiocpp-"))
  const runtime = join(root, "resources", "audiocpp")
  const audio = join(root, "audio")
  mkdirSync(runtime, { recursive: true })
  mkdirSync(audio, { recursive: true })
  writeFileSync(join(runtime, exe("audiocpp_server")), "")
  if (config) writeFileSync(join(audio, SERVER_CONFIG), '{"models":[]}')
  return {
    ctx: {
      packaged: true,
      backendDir: root,
      binariesDir: join(root, "resources"),
      host: "127.0.0.1",
      apiPort: 1,
      dataDir: root,
      secret: "s",
      audioPort: 9998,
      audioModelsDir: audio,
      audioBinariesDir: runtime,
    },
    audio,
  }
}

test("runs in dev too, because only the binary's path differs", () => {
  const { ctx } = staged()
  assert.ok(audiocppSpec({ ...ctx, packaged: false }))
})

test("does not run when the pinned build is not staged", () => {
  const { ctx } = staged()
  assert.equal(
    audiocppSpec({ ...ctx, audioBinariesDir: join(ctx.binariesDir, "absent") }),
    null
  )
})

test("does not run until the API has written its config", () => {
  // The server refuses an empty model list, measured, so it can only start
  // once an install has given the API a model to name.
  const { ctx } = staged({ config: false })
  assert.equal(audiocppSpec(ctx), null)
})

/** The value that follows a flag in a spec's args. */
function flag(args: string[], name: string): string | undefined {
  const at = args.indexOf(name)
  return at === -1 ? undefined : args[at + 1]
}

test("passes the machine-wide settings as flags, which win over the config", () => {
  // Measured: a --port or --backend on the command line overrides the config
  // file's, so Electron owns these and the API writes only the model list.
  const { ctx, audio } = staged()
  const spec = audiocppSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--config"), join(audio, SERVER_CONFIG))
  assert.equal(flag(spec.args, "--host"), "127.0.0.1")
  assert.equal(flag(spec.args, "--port"), "9998")
  assert.equal(flag(spec.args, "--max-loaded-models"), "1")
  assert.equal(flag(spec.args, "--idle-unload-ms"), "300000")
  assert.equal(flag(spec.args, "--min-free-memory-mb"), "1024")
  assert.ok(spec.args.includes("--no-ui"))
})

test("runs on the CPU, never on its CUDA default", () => {
  // audio.cpp defaults to CUDA; the GPU is the chat model's, and Metal waits
  // for a measurement on an Apple Silicon Mac.
  const { ctx } = staged()
  const spec = audiocppSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--backend"), "cpu")
})

test("uses half the logical cores, at most 8 and at least 1", () => {
  // Its default is one thread, which nearly doubled a passage's time. Every
  // core was slower and noisier than half, because ggml's workers spin while
  // they wait, and half leaves room for the chat model.
  assert.deepEqual([1, 2, 3, 4, 12, 16, 32].map(audioThreads), [1, 1, 1, 2, 6, 8, 8])
})

test("passes this machine's thread count", () => {
  const { ctx } = staged()
  const spec = audiocppSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--threads"), String(audioThreads(availableParallelism())))
})

test("points audio.cpp at the eSpeak staged beside it", () => {
  // Kokoro and Kitten phonemise through eSpeak-ng, which audio.cpp does not
  // ship. Measured without it: "eSpeak-ng library does not exist", no audio.
  // The names are the espeakng-loader 0.2.4 wheels' own.
  const library = {
    linux: "libespeak-ng.so",
    darwin: "libespeak-ng.dylib",
    win32: "espeak-ng.dll",
  }[process.platform as "linux" | "darwin" | "win32"]
  const { ctx } = staged()
  const spec = audiocppSpec(ctx)
  assert.ok(spec)
  const espeak = join(ctx.audioBinariesDir ?? "", "espeak")
  assert.equal(spec.env.AUDIOCPP_ESPEAK_LIBRARY, join(espeak, library))
  assert.equal(spec.env.AUDIOCPP_ESPEAK_DATA, join(espeak, "espeak-ng-data"))
})

test("runs from its own directory, where its ggml libraries are", () => {
  const { ctx } = staged()
  const spec = audiocppSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.cwd, ctx.audioBinariesDir)
})
