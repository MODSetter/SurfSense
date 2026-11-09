import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs"
import os, { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { AUDIOCPP_SIDECAR, audiocppSpec, SERVER_CONFIG } from "./audiocpp.ts"
import {
  AUDIOCPP_TRANSCRIPTION_SIDECAR,
  audiocppTranscriptionSpec,
  TRANSCRIPTION_CONFIG,
} from "./audiocpp-transcription.ts"
import { exe } from "./platform.ts"
import type { SidecarContext } from "./types.ts"

/** A staged build and an audio folder, with the API's transcription config written or not. */
function staged({ config = true, voices = false } = {}): {
  ctx: SidecarContext
  audio: string
} {
  const root = mkdtempSync(join(tmpdir(), "audiocpp-transcription-"))
  const runtime = join(root, "resources", "audiocpp")
  const audio = join(root, "audio")
  mkdirSync(runtime, { recursive: true })
  mkdirSync(audio, { recursive: true })
  writeFileSync(join(runtime, exe("audiocpp_server")), "")
  if (config) writeFileSync(join(audio, TRANSCRIPTION_CONFIG), '{"models":[]}')
  if (voices) writeFileSync(join(audio, SERVER_CONFIG), '{"models":[]}')
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
      transcriptionPort: 9997,
      audioModelsDir: audio,
      audioBinariesDir: runtime,
    },
    audio,
  }
}

/** The value that follows a flag in a spec's args. */
function flag(args: string[], name: string): string | undefined {
  const at = args.indexOf(name)
  return at === -1 ? undefined : args[at + 1]
}

test("runs the binary the voices' server runs, staged once", () => {
  const { ctx } = staged({ voices: true })
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.cmd, audiocppSpec(ctx)?.cmd)
})

test("runs beside the voices' server under a name of its own", () => {
  // The supervisor keys children by name: one name would make each replace the other.
  const { ctx } = staged({ voices: true })
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.name, AUDIOCPP_TRANSCRIPTION_SIDECAR)
  assert.notEqual(spec.name, AUDIOCPP_SIDECAR)
})

test("runs in dev too, because only the binary's path differs", () => {
  const { ctx } = staged()
  assert.ok(audiocppTranscriptionSpec({ ...ctx, packaged: false }))
})

test("does not run when the pinned build is not staged", () => {
  const { ctx } = staged()
  assert.equal(
    audiocppTranscriptionSpec({
      ...ctx,
      audioBinariesDir: join(ctx.binariesDir, "absent"),
    }),
    null
  )
})

test("does not run until the API names a speech model, whatever voices are installed", () => {
  // The server refuses an empty model list, and the voices' config is not its own.
  const { ctx } = staged({ config: false, voices: true })
  assert.equal(audiocppTranscriptionSpec(ctx), null)
})

test("reads its own config on its own port, so a voice install never restarts it", () => {
  const { ctx, audio } = staged({ voices: true })
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--config"), join(audio, TRANSCRIPTION_CONFIG))
  assert.equal(flag(spec.args, "--host"), "127.0.0.1")
  assert.equal(flag(spec.args, "--port"), "9997")
})

test("holds one speech model, unloads it after 5 idle minutes, and keeps 1 GiB free", () => {
  const { ctx } = staged()
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--max-loaded-models"), "1")
  assert.equal(flag(spec.args, "--idle-unload-ms"), "300000")
  assert.equal(flag(spec.args, "--min-free-memory-mb"), "1024")
  assert.ok(spec.args.includes("--no-ui"))
})

test("runs on the CPU, never on its CUDA default", () => {
  // The GPU is the chat model's (ADR 0012).
  const { ctx } = staged()
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(flag(spec.args, "--backend"), "cpu")
})

test("passes half of this machine's logical cores, capped at 8", (t) => {
  const { ctx } = staged()
  const threads = (cores: number) => {
    t.mock.method(os, "availableParallelism", () => cores)
    const spec = audiocppTranscriptionSpec(ctx)
    assert.ok(spec)
    return flag(spec.args, "--threads")
  }
  assert.equal(threads(12), "6")
  assert.equal(threads(32), "8")
})

test("is not pointed at eSpeak, which only the voices phonemise through", () => {
  const { ctx } = staged()
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.deepEqual(spec.env, {})
})

test("runs from its own directory, where its ggml libraries are", () => {
  const { ctx } = staged()
  const spec = audiocppTranscriptionSpec(ctx)
  assert.ok(spec)
  assert.equal(spec.cwd, ctx.audioBinariesDir)
})

test("does not run without a port of its own", () => {
  const { ctx } = staged()
  assert.equal(audiocppTranscriptionSpec({ ...ctx, transcriptionPort: undefined }), null)
})
