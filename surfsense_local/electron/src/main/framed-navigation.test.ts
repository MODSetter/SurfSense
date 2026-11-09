import assert from "node:assert/strict"
import test from "node:test"

import { frameMayNavigate } from "./framed-navigation.ts"

test("a viewer's frame may load the page the app gave it", () => {
  assert.equal(frameMayNavigate("about:srcdoc"), true)
  assert.equal(frameMayNavigate("about:blank"), true)
})

test("a frame may not navigate itself to a host, which could carry what it read", () => {
  assert.equal(frameMayNavigate("https://example.com/?d=secret"), false)
  assert.equal(frameMayNavigate("http://127.0.0.1:8000/artifacts/1"), false)
  assert.equal(frameMayNavigate("file:///etc/hosts"), false)
})

test("nor to a script or data URL, nor to anything that is not a URL", () => {
  assert.equal(frameMayNavigate("javascript:alert(1)"), false)
  assert.equal(frameMayNavigate("data:text/html,<p>x</p>"), false)
  assert.equal(frameMayNavigate("not a url"), false)
})
