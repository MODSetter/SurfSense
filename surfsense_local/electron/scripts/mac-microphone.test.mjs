import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

const read = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n")

// Under the hardened runtime, askForMediaAccess without the entitlement can crash
// the app, and without the usage string it shows Electron's own sentence.
test("the macOS build may use the microphone, and says why it asks", () => {
  const entitlements = read("../build/entitlements.mac.plist")
  assert.match(
    entitlements,
    /<key>com\.apple\.security\.device\.audio-input<\/key>\s*<true\/>/
  )

  const yml = read("../electron-builder.yml")
  const mac = yml.match(/^mac:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  assert.match(mac, /^  entitlementsInherit: build\/entitlements\.mac\.plist$/m)
  assert.match(
    mac,
    /^  extendInfo:\n    NSMicrophoneUsageDescription: "SurfSense turns your speech into text on this computer\."$/m
  )
})
