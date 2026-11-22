/**
 * The boot context the container answers from its environment, where Electron
 * answers from app.isPackaged and resourcesPath. The defaults are the tree
 * beside this file, which is a checkout's layout and the image's.
 */
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import type { BootContext } from "../sidecars/boot.ts"

const LOCAL = fileURLToPath(new URL("..", import.meta.url))

type Env = Record<string, string | undefined>

/** An empty variable counts as unset. */
function named(env: Env, key: string): string | undefined {
  return env[key] || undefined
}

export function contextFromEnv(env: Env, secret: string): BootContext {
  const backendDir = named(env, "SURFSENSE_LOCAL_BACKEND_DIR") ?? join(LOCAL, "backend")
  // runtimes/ stages into electron/<runtime>/ unless told otherwise.
  const runtimes = named(env, "SURFSENSE_LOCAL_RUNTIMES_DIR") ?? join(LOCAL, "electron")
  return {
    // A venv backend, not the frozen one: the image runs from source.
    packaged: false,
    backendDir,
    binariesDir: LOCAL,
    dataDir: named(env, "SURFSENSE_LOCAL_DATA_DIR") ?? "/data",
    secret,
    modelsDir: named(env, "SURFSENSE_LOCAL_MODELS_DIR") ?? join(LOCAL, "backend", "models"),
    llamacppBinariesDir: join(runtimes, "llamacpp"),
    audioBinariesDir: join(runtimes, "audiocpp"),
    sdcppBinariesDir: join(runtimes, "sdcpp"),
    opencodeBinariesDir: join(runtimes, "opencode"),
  }
}
