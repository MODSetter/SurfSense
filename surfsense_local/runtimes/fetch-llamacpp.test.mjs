import assert from "node:assert/strict"
import { test } from "node:test"

import { BUILD, checkConfiguration, pinnedBuild } from "./fetch-llamacpp.mjs"

test("with no variant, a host stages the desktop's build, Vulkan on Linux", () => {
  assert.match(pinnedBuild("linux-x64").asset, /ubuntu-vulkan-x64/)
  assert.match(pinnedBuild("win32-x64").asset, /win-vulkan-x64/)
  assert.match(pinnedBuild("darwin-arm64").asset, /macos-arm64/)
})

test("the Docker image's CPU variant is upstream's plain Ubuntu build at the same pin", () => {
  const cpu = pinnedBuild("linux-x64", "cpu")
  assert.equal(cpu.asset, `llama-${BUILD}-bin-ubuntu-x64.tar.gz`)
  assert.match(cpu.sha256, /^[0-9a-f]{64}$/)
})

test("an unknown target or variant is refused rather than guessed", () => {
  assert.throws(() => pinnedBuild("linux-x64", "rocm"), /no pinned llama.cpp/)
  assert.throws(() => pinnedBuild("freebsd-x64"), /no pinned llama.cpp/)
})

test("the pinned matrix is consistent", () => {
  assert.doesNotThrow(() => checkConfiguration())
})
