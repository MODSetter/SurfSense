import assert from "node:assert/strict"
import test from "node:test"

import { channelFile, feedBase, GITHUB_LATEST_DOWNLOAD, githubReleaseDownload } from "./feed-addresses.ts"

test("asks for the release channel's signed manifest under electron-builder's own names", () => {
  assert.equal(channelFile("win32", "x64"), "release.yml")
  assert.equal(channelFile("win32", "arm64"), "release.yml")
  assert.equal(channelFile("darwin", "arm64"), "release-mac.yml")
  assert.equal(channelFile("linux", "x64"), "release-linux.yml")
  assert.equal(channelFile("linux", "arm64"), "release-linux-arm64.yml")
})

test("manifests come from GitHub's Latest release, installers from the release a version names", () => {
  assert.equal(GITHUB_LATEST_DOWNLOAD, "https://github.com/MODSetter/SurfSense/releases/latest/download/")
  assert.equal(
    githubReleaseDownload("2.4.0"),
    "https://github.com/MODSetter/SurfSense/releases/download/v2.4.0/"
  )
  assert.equal(feedBase("https://mirror.example/updates"), "https://mirror.example/updates/")
  assert.equal(feedBase("https://mirror.example/updates/"), "https://mirror.example/updates/")
})
