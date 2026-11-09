import assert from "node:assert/strict"
import { mkdtempSync, readdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import test from "node:test"

import {
  LOCATION_FILE,
  readStorageLocation,
  writeStorageLocation,
} from "./location-file.ts"

const base = () => mkdtempSync(join(tmpdir(), "surfsense-location-"))

test("an install that never moved anything has no location", () => {
  assert.deepEqual(readStorageLocation(base()), {})
})

test("a saved location reads back, and no temporary file stays beside it", () => {
  const dir = base()
  const location = {
    dataRoot: resolve("drive", "SurfSense-Data"),
    modelsRoot: resolve("other", "SurfSense-Models"),
    leftBehind: [{ root: resolve("old"), entries: ["models", "audio"] }],
  }
  writeStorageLocation(dir, location)
  assert.deepEqual(readStorageLocation(dir), location)
  assert.deepEqual(readdirSync(dir), [LOCATION_FILE])
})

test("a damaged file reads as no location rather than failing the start", () => {
  const dir = base()
  writeFileSync(join(dir, LOCATION_FILE), "{not json")
  assert.deepEqual(readStorageLocation(dir), {})
})

test("a relative folder is ignored: it would resolve against whatever the cwd is", () => {
  const dir = base()
  writeFileSync(join(dir, LOCATION_FILE), JSON.stringify({ dataRoot: "SurfSense-Data" }))
  assert.deepEqual(readStorageLocation(dir), {})
})

test("a left-behind entry that is not a bare name is dropped: it decides what gets deleted", () => {
  const dir = base()
  writeFileSync(
    join(dir, LOCATION_FILE),
    JSON.stringify({
      leftBehind: [{ root: resolve("old"), entries: ["models", "../../home", "a/b", "..", ""] }],
    })
  )
  assert.deepEqual(readStorageLocation(dir).leftBehind, [
    { root: resolve("old"), entries: ["models"] },
  ])
})
