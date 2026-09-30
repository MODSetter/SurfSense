import assert from "node:assert/strict"
import test from "node:test"

import { allowedExternalUrl } from "./external-url.ts"

test("opens the SurfSense site", () => {
  assert.equal(
    allowedExternalUrl("https://www.surfsense.com/docs"),
    "https://www.surfsense.com/docs"
  )
  assert.equal(
    allowedExternalUrl("https://surfsense.com/sunset"),
    "https://surfsense.com/sunset"
  )
})

test("opens the project's GitHub repository and nothing else on GitHub", () => {
  assert.equal(
    allowedExternalUrl(
      "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2"
    ),
    "https://github.com/MODSetter/SurfSense/releases/tag/v2.0.2"
  )
  assert.equal(
    allowedExternalUrl("https://github.com/MODSetter/SurfSense"),
    "https://github.com/MODSetter/SurfSense"
  )
  assert.equal(allowedExternalUrl("https://github.com/MODSetter"), null)
  assert.equal(
    allowedExternalUrl("https://github.com/MODSetter/SurfSense-evil"),
    null
  )
  assert.equal(allowedExternalUrl("https://github.com/someone/else"), null)
})

test("opens the community Discord invite only", () => {
  assert.equal(
    allowedExternalUrl("https://discord.gg/ejRNvftDp9"),
    "https://discord.gg/ejRNvftDp9"
  )
  assert.equal(allowedExternalUrl("https://discord.gg/other"), null)
})

test("opens OpenRouter's two-segment pages, as a model's is, and no other shape", () => {
  assert.equal(
    allowedExternalUrl("https://openrouter.ai/hexgrad/kokoro-82m"),
    "https://openrouter.ai/hexgrad/kokoro-82m"
  )
  assert.equal(
    allowedExternalUrl("https://openrouter.ai/bytedance-seed/seed-audio-1-0"),
    "https://openrouter.ai/bytedance-seed/seed-audio-1-0"
  )
  assert.equal(allowedExternalUrl("https://openrouter.ai/"), null)
  assert.equal(allowedExternalUrl("https://openrouter.ai/a/b/c"), null)
  assert.equal(allowedExternalUrl("https://openrouter.ai/a/b?x=1"), null)
  assert.equal(allowedExternalUrl("https://evil.openrouter.ai/a/b"), null)
})

test("refuses other schemes and hosts", () => {
  assert.equal(allowedExternalUrl("http://surfsense.com"), null)
  assert.equal(allowedExternalUrl("file:///etc/passwd"), null)
  assert.equal(allowedExternalUrl("https://evil.surfsense.com.example"), null)
  assert.equal(allowedExternalUrl("not a url"), null)
})
