import assert from "node:assert/strict"
import test from "node:test"

import { HOSTS, RIPGREP_VERSION, VERSION } from "./pins.mjs"

const SHIPPED = ["darwin-arm64", "linux-x64", "win32-x64"]

test("every platform the app ships has opencode and ripgrep pinned", () => {
  assert.deepEqual(Object.keys(HOSTS).sort(), SHIPPED)
  for (const host of SHIPPED) {
    for (const tool of ["opencode", "ripgrep"]) {
      assert.match(HOSTS[host][tool].sha256, /^[0-9a-f]{64}$/, `${host} ${tool}`)
    }
  }
})

test("each archive is the pinned version's", () => {
  for (const host of SHIPPED) {
    assert.match(HOSTS[host].opencode.url, new RegExp(`/v${VERSION}/`), host)
    assert.match(HOSTS[host].ripgrep.url, new RegExp(`/${RIPGREP_VERSION}/`), host)
  }
})

test("x64 takes the build made without AVX2, so older CPUs run it", () => {
  for (const host of ["linux-x64", "win32-x64"]) {
    assert.match(HOSTS[host].opencode.url, /-x64-baseline\./, host)
  }
})
