import assert from "node:assert/strict"
import { join } from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"

import { contextFromEnv } from "./context-from-env.ts"

const LOCAL = fileURLToPath(new URL("..", import.meta.url))

test("with nothing set, the tree beside it and /data: the image's layout and a checkout's", () => {
  assert.deepEqual(contextFromEnv({}, "the-secret"), {
    packaged: false,
    backendDir: join(LOCAL, "backend"),
    binariesDir: LOCAL,
    dataDir: "/data",
    secret: "the-secret", // pragma: allowlist secret
    modelsDir: join(LOCAL, "backend", "models"),
    llamacppBinariesDir: join(LOCAL, "electron", "llamacpp"),
    audioBinariesDir: join(LOCAL, "electron", "audiocpp"),
    sdcppBinariesDir: join(LOCAL, "electron", "sdcpp"),
    opencodeBinariesDir: join(LOCAL, "electron", "opencode"),
  })
})

test("each folder can be named in the environment", () => {
  const context = contextFromEnv(
    {
      SURFSENSE_LOCAL_BACKEND_DIR: "/srv/backend",
      SURFSENSE_LOCAL_DATA_DIR: "/srv/data",
      SURFSENSE_LOCAL_MODELS_DIR: "/srv/models",
      SURFSENSE_LOCAL_RUNTIMES_DIR: "/srv/runtimes",
    },
    "the-secret",
  )
  assert.equal(context.backendDir, "/srv/backend")
  assert.equal(context.dataDir, "/srv/data")
  assert.equal(context.modelsDir, "/srv/models")
  assert.equal(context.llamacppBinariesDir, join("/srv/runtimes", "llamacpp"))
  assert.equal(context.audioBinariesDir, join("/srv/runtimes", "audiocpp"))
  assert.equal(context.sdcppBinariesDir, join("/srv/runtimes", "sdcpp"))
  assert.equal(context.opencodeBinariesDir, join("/srv/runtimes", "opencode"))
})

test("an empty variable is unset, not a folder named nothing", () => {
  assert.equal(contextFromEnv({ SURFSENSE_LOCAL_DATA_DIR: "" }, "s").dataDir, "/data")
})
