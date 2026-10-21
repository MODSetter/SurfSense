import assert from "node:assert/strict"
import test from "node:test"

import { captureHeight, CAPTURE_WIDTH } from "./capture-size.ts"

test("a page is captured at the viewer's width", () => {
  assert.equal(CAPTURE_WIDTH, 1280)
})

test("a page is captured as tall as it is, up to four screens", () => {
  assert.equal(captureHeight(2500), 2500)
  assert.equal(captureHeight(12000), 4000)
})

test("a short page is captured as one full screen", () => {
  assert.equal(captureHeight(300), 1000)
})

test("a height the page reports wrongly is a single screen", () => {
  assert.equal(captureHeight("tall"), 1000)
  assert.equal(captureHeight(Number.NaN), 1000)
  assert.equal(captureHeight(-5), 1000)
  assert.equal(captureHeight(2400.4), 2401)
})
