import assert from "node:assert/strict"
import test from "node:test"

import { loaderRan, probeVerdict, unprovenFamilies } from "./built-families.mjs"

// What audiocpp_server v0.8.2 printed when started on an empty model package,
// measured on Windows builds with and without each family.
const BUILT =
  "audiocpp_server failed: failed to load model resources using builtin model spec for family " +
  "'nemotron_asr' source 'gguf': missing model package file 'config': C:\\probe\\config.json"
const LEFT_OUT = "audiocpp_server failed: unsupported model family hint: nemotron_asr"

test("a family's loader reaching the empty package proves it was built", () => {
  assert.equal(loaderRan("nemotron_asr", BUILT), true)
})

test("a family the build left out is refused by name before any loader runs", () => {
  assert.equal(loaderRan("nemotron_asr", LEFT_OUT), false)
})

test("another family's loader proves nothing about this one", () => {
  assert.equal(loaderRan("kokoro_tts", BUILT), false)
})

test("reads a family's probe as built, left out of the build, or never reached", () => {
  assert.equal(probeVerdict("nemotron_asr", BUILT), "built")
  assert.equal(probeVerdict("nemotron_asr", LEFT_OUT), "missing")
  // A server that cannot start at all (blocked, a library missing) printed nothing
  // about any family: it is not evidence of a build without them.
  assert.equal(probeVerdict("nemotron_asr", ""), "unknown")
})

/** A stand-in for starting the server: what a build with only `built` prints. */
function serverBuiltWith(built) {
  return async (_stage, _work, family) =>
    built.includes(family)
      ? `audiocpp_server failed: failed to load model resources using builtin model spec for family '${family}' source 'gguf'`
      : `audiocpp_server failed: unsupported model family hint: ${family}`
}

test("names every curated family a staged server was built without, with what it printed", async () => {
  // A checkout staged before canary_asr joined the pins: the server says
  // "unsupported model family hint: canary_asr" and speech cannot load.
  const unproven = await unprovenFamilies("stage", {
    families: ["kokoro_tts", "nemotron_asr", "canary_asr"],
    load: serverBuiltWith(["kokoro_tts", "nemotron_asr"]),
  })
  assert.deepEqual(
    unproven.map(({ family, verdict }) => [family, verdict]),
    [["canary_asr", "missing"]]
  )
  assert.match(unproven[0].output, /unsupported model family hint: canary_asr/)
})

test("proves every family of a server built with all of them", async () => {
  const unproven = await unprovenFamilies("stage", {
    families: ["kokoro_tts", "canary_asr"],
    load: serverBuiltWith(["kokoro_tts", "canary_asr"]),
  })
  assert.deepEqual(unproven, [])
})
