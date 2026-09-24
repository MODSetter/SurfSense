/**
 * audio.cpp's server: local audio generation, for podcast voices. It refuses an
 * empty model list, so it runs only once the API has written its config, and
 * index.ts restarts it whenever the API rewrites that file.
 */
import { existsSync } from "node:fs"
import { availableParallelism } from "node:os"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const AUDIOCPP_SIDECAR = "audiocpp"

/** The model list the API writes; command-line flags override the rest of it. */
export const SERVER_CONFIG = "server.json"

/** eSpeak-ng as fetch-audiocpp.mjs stages it, from the espeakng-loader wheel. */
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
      String(audioThreads(availableParallelism())),
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
    // Kokoro and Kitten phonemise through eSpeak-ng, which audio.cpp loads at
    // run time and does not ship.
    env: {
      AUDIOCPP_ESPEAK_LIBRARY: join(
        ctx.audioBinariesDir,
        ESPEAK_DIR,
        ESPEAK_LIBRARY[process.platform] ?? ESPEAK_LIBRARY.linux
      ),
      AUDIOCPP_ESPEAK_DATA: join(ctx.audioBinariesDir, ESPEAK_DIR, "espeak-ng-data"),
    },
  }
}
