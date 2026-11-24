import assert from "node:assert/strict"
import { join } from "node:path"
import test from "node:test"

import { MODEL_FOLDER_NAMES, modelFolders } from "./model-folders.ts"

test("every kind of downloaded model has its folder under the one root", () => {
  const root = join("drive", "SurfSense-Models")
  assert.deepEqual(modelFolders(root), {
    generation: join(root, "models"),
    audio: join(root, "audio"),
    images: join(root, "images"),
    embeddings: join(root, "embeddings"),
  })
})

test("the mover and the boot agree on the four folders", () => {
  assert.deepEqual([...MODEL_FOLDER_NAMES].sort(), ["audio", "embeddings", "images", "models"])
})
