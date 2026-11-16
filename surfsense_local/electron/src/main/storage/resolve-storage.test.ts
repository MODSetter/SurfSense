import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { writeMarker } from "./marker.ts"
import { resolveStorage } from "./resolve-storage.ts"

const temp = () => mkdtempSync(join(tmpdir(), "surfsense-resolve-"))

test("nothing moved: data and models are both in the fixed folder, and always reachable", () => {
  const base = temp()
  assert.deepEqual(resolveStorage(base, {}), {
    baseDir: base,
    dataRoot: base,
    modelsRoot: base,
    dataMoved: false,
    modelsMoved: false,
    dataReachable: true,
    modelsReachable: true,
  })
})

test("models follow the data folder until they are moved on their own", () => {
  const base = temp()
  const dataRoot = temp()
  writeMarker(dataRoot, "data")
  const storage = resolveStorage(base, { dataRoot })
  assert.equal(storage.dataRoot, dataRoot)
  assert.equal(storage.modelsRoot, dataRoot)
  assert.equal(storage.modelsMoved, false)
})

test("an empty mount point is not the chosen folder: no marker, not reachable", () => {
  const base = temp()
  const emptyMountPoint = join(temp(), "usb")
  mkdirSync(emptyMountPoint)
  const storage = resolveStorage(base, { dataRoot: emptyMountPoint, modelsRoot: emptyMountPoint })
  assert.equal(storage.dataReachable, false)
  assert.equal(storage.modelsReachable, false)
})

test("the data folder's marker does not vouch for a models folder", () => {
  const base = temp()
  const root = temp()
  writeMarker(root, "data")
  assert.equal(resolveStorage(base, { modelsRoot: root }).modelsReachable, false)
})
