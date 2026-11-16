import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { readStorageLocation, writeStorageLocation } from "./location-file.ts"
import { writeMarker } from "./marker.ts"
import { settleStorageBeforeBoot, type DrivePrompts } from "./settle-before-boot.ts"

const temp = () => mkdtempSync(join(tmpdir(), "surfsense-settle-"))

function prompts(answers: Partial<DrivePrompts> = {}): DrivePrompts & { asked: string[] } {
  const asked: string[] = []
  return {
    asked,
    dataMissing: answers.dataMissing ?? (async (path) => { asked.push(`data:${path}`); return "quit" }),
    modelsMissing: answers.modelsMissing ?? (async (path) => { asked.push(`models:${path}`); return "quit" }),
    pickDataFolder: answers.pickDataFolder ?? (async () => null),
    notADataFolder: answers.notADataFolder ?? (async () => { asked.push("not-a-data-folder") }),
  }
}

test("nothing moved: no question is asked", async () => {
  const ask = prompts()
  const settled = await settleStorageBeforeBoot(temp(), ask)
  assert.equal(settled?.modelsUnavailable, false)
  assert.deepEqual(ask.asked, [])
})

test("a missing data folder stops the start: an empty database would look like data loss", async () => {
  const base = temp()
  writeStorageLocation(base, { dataRoot: join(temp(), "gone") })
  const settled = await settleStorageBeforeBoot(base, prompts())
  assert.equal(settled, null)
})

test("retry finds the drive once it is back", async () => {
  const base = temp()
  const root = temp()
  writeStorageLocation(base, { dataRoot: root })
  const settled = await settleStorageBeforeBoot(base, prompts({
    dataMissing: async () => {
      writeMarker(root, "data")
      return "retry"
    },
  }))
  assert.equal(settled?.storage.dataRoot, root)
})

test("choosing the folder that holds the data, or the data folder itself, repoints to it", async () => {
  for (const pickParent of [true, false]) {
    const base = temp()
    const parent = temp()
    const root = join(parent, "SurfSense-Data")
    mkdirSync(root)
    writeMarker(root, "data")
    writeStorageLocation(base, { dataRoot: join(temp(), "old-letter") })
    let asked = 0
    const settled = await settleStorageBeforeBoot(base, prompts({
      dataMissing: async () => (asked++ === 0 ? "choose" : "quit"),
      pickDataFolder: async () => (pickParent ? parent : root),
    }))
    assert.equal(settled?.storage.dataRoot, root)
    assert.equal(readStorageLocation(base).dataRoot, root)
  }
})

test("a chosen folder without SurfSense's data is refused, not started empty", async () => {
  const base = temp()
  const gone = join(temp(), "gone")
  writeStorageLocation(base, { dataRoot: gone })
  let asked = 0
  const ask = prompts({
    dataMissing: async () => (asked++ === 0 ? "choose" : "quit"),
    pickDataFolder: async () => temp(),
  })
  assert.equal(await settleStorageBeforeBoot(base, ask), null)
  assert.deepEqual(ask.asked, ["not-a-data-folder"])
  assert.equal(readStorageLocation(base).dataRoot, gone)
})

test("a missing models drive can be passed by: the rest of the app still works", async () => {
  const base = temp()
  const modelsRoot = join(temp(), "gone")
  writeStorageLocation(base, { modelsRoot })
  const settled = await settleStorageBeforeBoot(base, prompts({ modelsMissing: async () => "continue" }))
  assert.equal(settled?.modelsUnavailable, true)
  assert.equal(readStorageLocation(base).modelsRoot, modelsRoot)
})

test("quitting at the missing models drive quits", async () => {
  const base = temp()
  writeStorageLocation(base, { modelsRoot: join(temp(), "gone") })
  assert.equal(await settleStorageBeforeBoot(base, prompts()), null)
})
