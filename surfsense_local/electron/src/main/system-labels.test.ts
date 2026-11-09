import assert from "node:assert/strict"
import test from "node:test"

import { osLabel, platformLabel } from "./system-labels.ts"

test("names the platforms SurfSense ships for, and nothing else", () => {
  assert.equal(platformLabel("win32", "x64"), "win32-x64")
  assert.equal(platformLabel("darwin", "arm64"), "darwin-arm64")
  assert.equal(platformLabel("linux", "arm64"), "linux-arm64")
  assert.equal(platformLabel("win32", "ia32"), null)
  assert.equal(platformLabel("freebsd", "x64"), null)
})

test("tells Windows 11 from 10 by build, and keeps only macOS's major version", () => {
  assert.equal(osLabel("win32", "10.0.22631"), "windows-11")
  assert.equal(osLabel("win32", "10.0.19045"), "windows-10")
  assert.equal(osLabel("win32", "6.3.9600"), null)
  assert.equal(osLabel("darwin", "15.1.0"), "macos-15")
  assert.equal(osLabel("darwin", ""), null)
  assert.equal(osLabel("linux", "6.8.0-45-generic"), "linux")
})
