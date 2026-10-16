import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { copyServerFiles, SERVER } from "./server-files.mjs"

/** A build folder and a source checkout carrying more model specs than the app curates. */
function built() {
  const root = mkdtempSync(join(tmpdir(), "audiocpp-files-"))
  const binaries = join(root, "build", "bin", "Release")
  const source = join(root, "source")
  const stage = join(root, "stage")
  mkdirSync(binaries, { recursive: true })
  mkdirSync(join(source, "model_specs"), { recursive: true })
  mkdirSync(stage)
  writeFileSync(join(binaries, SERVER), "")
  writeFileSync(join(source, "LICENSE"), "MIT")
  for (const family of [
    "kokoro_tts",
    "supertonic",
    "kitten_tts",
    "nemotron_asr",
    "canary_asr",
    "qwen3_asr",
  ]) {
    writeFileSync(join(source, "model_specs", `${family}.json`), "{}")
  }
  return { files: { binaries, source }, stage }
}

test("ships the voices' and the recognisers' specs, and no other family's", () => {
  const { files, stage } = built()

  copyServerFiles(files, stage)

  assert.deepEqual(readdirSync(join(stage, "model_specs")).sort(), [
    "canary_asr.json",
    "kitten_tts.json",
    "kokoro_tts.json",
    "nemotron_asr.json",
    "supertonic.json",
  ])
})
