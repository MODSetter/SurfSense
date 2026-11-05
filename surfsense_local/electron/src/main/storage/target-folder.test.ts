import assert from "node:assert/strict"
import { posix, win32 } from "node:path"
import test from "node:test"

import { refusalForTarget, targetRoot } from "./target-folder.ts"

const occupied = { baseDir: "/home/me/.surfsense", dataRoot: "/home/me/.surfsense", modelsRoot: "/home/me/.surfsense" }

test("the app makes its own folder, so a move never mixes with the user's files", () => {
  assert.equal(targetRoot("models", "/mnt/big", false, posix), "/mnt/big/SurfSense-Models")
  assert.equal(targetRoot("data", "/mnt/big", false, posix), "/mnt/big/SurfSense-Data")
})

test("picking the app's own folder, or one already marked, uses it as it is", () => {
  assert.equal(targetRoot("models", "/mnt/big/SurfSense-Models", false, posix), "/mnt/big/SurfSense-Models")
  assert.equal(targetRoot("models", "/mnt/big/old-name", true, posix), "/mnt/big/old-name")
})

test("a drive's root on Windows takes the subfolder too", () => {
  assert.equal(targetRoot("models", "D:\\", false, win32), "D:\\SurfSense-Models")
})

test("a folder inside the current data folder is refused: the move would copy into itself", () => {
  const refusal = refusalForTarget({
    kind: "models",
    root: "/home/me/.surfsense/sub/SurfSense-Models",
    ...occupied,
    appFolder: "/opt/SurfSense",
    paths: posix,
  })
  assert.equal(refusal, "inside_current")
})

test("a folder inside the app is refused: an update would delete it", () => {
  const refusal = refusalForTarget({
    kind: "models",
    root: "/opt/SurfSense/resources/SurfSense-Models",
    ...occupied,
    appFolder: "/opt/SurfSense",
    paths: posix,
  })
  assert.equal(refusal, "inside_app")
})

test("the folder it already uses is not a move", () => {
  const refusal = refusalForTarget({
    kind: "models",
    root: "/mnt/big/SurfSense-Models",
    baseDir: "/home/me/.surfsense",
    dataRoot: "/home/me/.surfsense",
    modelsRoot: "/mnt/big/SurfSense-Models",
    appFolder: "/opt/SurfSense",
    paths: posix,
  })
  assert.equal(refusal, "same_folder")
})

test("a sibling with a shared prefix is a different folder", () => {
  const refusal = refusalForTarget({
    kind: "models",
    root: "/home/me/.surfsense-other/SurfSense-Models",
    ...occupied,
    appFolder: "/opt/SurfSense",
    paths: posix,
  })
  assert.equal(refusal, null)
})

test("Windows paths compare without regard to case", () => {
  const refusal = refusalForTarget({
    kind: "models",
    root: "c:\\USERS\\me\\.SurfSense\\sub\\SurfSense-Models",
    baseDir: "C:\\Users\\me\\.surfsense",
    dataRoot: "C:\\Users\\me\\.surfsense",
    modelsRoot: "C:\\Users\\me\\.surfsense",
    appFolder: "C:\\Program Files\\SurfSense",
    paths: win32,
  })
  assert.equal(refusal, "inside_current")
})

test("a network share is refused for the data folder, whose databases need local locks", () => {
  const base = { baseDir: "C:\\s", dataRoot: "C:\\s", modelsRoot: "C:\\s", appFolder: "C:\\a", paths: win32 }
  assert.equal(refusalForTarget({ ...base, kind: "data", root: "\\\\nas\\share\\SurfSense-Data" }), "network_drive")
  assert.equal(refusalForTarget({ ...base, kind: "models", root: "\\\\nas\\share\\SurfSense-Models" }), null)
})
