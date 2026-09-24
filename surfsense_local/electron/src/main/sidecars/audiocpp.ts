/**
 * audio.cpp's server: local audio generation, for podcast voices. It refuses an
 * empty model list, so it runs only once the API has written its config, and
 * index.ts restarts it whenever the API rewrites that file.
 */
import { existsSync } from "node:fs"
import os from "node:os"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const AUDIOCPP_SIDECAR = "audiocpp"

/** The model list the API writes; command-line flags override the rest of it. */
export const SERVER_CONFIG = "server.json"

/** eSpeak-ng as scripts/audiocpp/espeak.mjs stages it, from the espeakng-loader wheel. */
const ESPEAK_DIR = "espeak"
const ESPEAK_LIBRARY: Record<string, string> = {
  linux: "libespeak-ng.so",
  darwin: "libespeak-ng.dylib",
  win32: "espeak-ng.dll",
}

/**
 * Half the logical cores, at most 8. Measured, one thread nearly doubled a
 * passage's time, and every core was slower and noisier than half: ggml's
 * workers spin while they wait, and the chat model needs cores too.
 */
export function audioThreads(logicalCores: number): number {
  return Math.max(1, Math.min(8, Math.floor(logicalCores / 2)))
}

/** The staged eSpeak-ng, which the server and the API both need to name. */
export function espeakPaths(audioBinariesDir: string): { library: string; data: string } {
  return {
    library: join(
      audioBinariesDir,
      ESPEAK_DIR,
      ESPEAK_LIBRARY[process.platform] ?? ESPEAK_LIBRARY.linux
    ),
    data: join(audioBinariesDir, ESPEAK_DIR, "espeak-ng-data"),
  }
}

export function binaryPath(ctx: SidecarContext): string {
  return join(ctx.audioBinariesDir ?? "", exe("audiocpp_server"))
}

export function audiocppSpec(ctx: SidecarContext): SidecarSpec | null {
  if (
    ctx.audioPort == null ||
    ctx.audioModelsDir == null ||
    ctx.audioBinariesDir == null
  ) {
    return null
  }
  const binary = binaryPath(ctx)
  const config = join(ctx.audioModelsDir, SERVER_CONFIG)
  if (!existsSync(binary) || !existsSync(config)) return null

  return {
    name: AUDIOCPP_SIDECAR,
    cmd: binary,
    // Measured: these flags win over the config file, so Electron owns them and
    // the API writes only the model list.
    args: [
      "--config",
      config,
      "--host",
      ctx.host,
      "--port",
      String(ctx.audioPort),
      // Its default is CUDA. The GPU is the chat model's, and Metal waits for a
      // measurement on an Apple Silicon Mac.
      "--backend",
      "cpu",
      "--threads",
      String(audioThreads(os.availableParallelism())),
      // One voice model at a time; the podcast job unloads it when it ends, and
      // five idle minutes are the backstop for a job that dies first.
      "--max-loaded-models",
      "1",
      "--idle-unload-ms",
      "300000",
      // Its estimate counts only the file it reads; the API checks the model's
      // measured peak first, so this is a backstop.
      "--min-free-memory-mb",
      "1024",
      "--no-ui",
    ],
    // ggml loads its backend libraries from beside the executable.
    cwd: ctx.audioBinariesDir,
    // Kokoro phonemises through eSpeak-ng, which audio.cpp loads at run time
    // and does not ship, and finds it here; Kitten reads the API's config.
    env: {
      AUDIOCPP_ESPEAK_LIBRARY: espeakPaths(ctx.audioBinariesDir).library,
      AUDIOCPP_ESPEAK_DATA: espeakPaths(ctx.audioBinariesDir).data,
    },
  }
}
