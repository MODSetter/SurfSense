import assert from "node:assert/strict"
import test from "node:test"

import { loaderRan } from "./built-families.mjs"

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
