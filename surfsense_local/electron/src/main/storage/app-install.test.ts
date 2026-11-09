import assert from "node:assert/strict"
import { posix, win32 } from "node:path"
import test from "node:test"

import { appInstallFolder, relaunchOptions } from "./app-install.ts"

test("on macOS the app is its whole bundle: an update replaces all of it", () => {
  assert.equal(
    appInstallFolder("darwin", "/Applications/SurfSense.app/Contents/MacOS/SurfSense", posix),
    "/Applications/SurfSense.app",
  )
})

test("elsewhere the app is the folder its executable is in", () => {
  assert.equal(appInstallFolder("linux", "/opt/SurfSense/surfsense-local", posix), "/opt/SurfSense")
  assert.equal(
    appInstallFolder("win32", "C:\\Users\\ana\\AppData\\Local\\Programs\\SurfSense\\SurfSense.exe", win32),
    "C:\\Users\\ana\\AppData\\Local\\Programs\\SurfSense",
  )
})

test("an AppImage relaunches from its file: its running path is a mount that goes when it exits", () => {
  assert.deepEqual(relaunchOptions({ APPIMAGE: "/home/ana/SurfSense.AppImage" }), {
    execPath: "/home/ana/SurfSense.AppImage",
  })
})

test("every other install relaunches as it started", () => {
  assert.deepEqual(relaunchOptions({}), {})
  assert.deepEqual(relaunchOptions({ APPIMAGE: "" }), {})
})
