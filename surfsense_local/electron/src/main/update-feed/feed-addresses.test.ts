import assert from "node:assert/strict"
import test from "node:test"

import { channelFile, feedBase, githubReleaseDownload } from "./feed-addresses.ts"

test("asks for the stable channel's manifest under electron-updater's own names", () => {
  assert.equal(channelFile("win32", "x64"), "stable.yml")
  assert.equal(channelFile("win32", "arm64"), "stable.yml")
  assert.equal(channelFile("darwin", "arm64"), "stable-mac.yml")
  assert.equal(channelFile("linux", "x64"), "stable-linux.yml")
  assert.equal(channelFile("linux", "arm64"), "stable-linux-arm64.yml")
})

test("installers come from the tagged release, and a mirror base always ends in a slash", () => {
  assert.equal(
    githubReleaseDownload("2.2.4"),
    "https://github.com/MODSetter/SurfSense/releases/download/v2.2.4/"
  )
  assert.equal(feedBase("https://mirror.example/updates"), "https://mirror.example/updates/")
  assert.equal(feedBase("https://mirror.example/updates/"), "https://mirror.example/updates/")
})
