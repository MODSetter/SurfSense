/**
 * audio.cpp's server a second time, for speech recognition. Its own process,
 * config and port keep a voice install, a podcast's unload or a busy voice
 * model from touching a transcription, and the reverse. Only the API calls it.
 */
import { existsSync } from "node:fs"
import os from "node:os"
import { join } from "node:path"

import { audioThreads, binaryPath } from "./audiocpp.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const AUDIOCPP_TRANSCRIPTION_SIDECAR = "audiocpp-transcription"

/** The speech models the API writes, beside the voices' server.json. */
export const TRANSCRIPTION_CONFIG = "transcription.json"

export function audiocppTranscriptionSpec(ctx: SidecarContext): SidecarSpec | null {
  if (
    ctx.transcriptionPort == null ||
    ctx.audioModelsDir == null ||
    ctx.audioBinariesDir == null
  ) {
    return null
  }
  const binary = binaryPath(ctx)
  const config = join(ctx.audioModelsDir, TRANSCRIPTION_CONFIG)
  // It refuses an empty model list, so it waits for the API to name one.
  if (!existsSync(binary) || !existsSync(config)) return null

  return {
    name: AUDIOCPP_TRANSCRIPTION_SIDECAR,
    cmd: binary,
    // These win over the config file, as for the voices' server.
    args: [
      "--config",
      config,
      "--host",
      ctx.host,
      "--port",
      String(ctx.transcriptionPort),
      // The GPU is the chat model's.
      "--backend",
      "cpu",
      "--threads",
      String(audioThreads(os.availableParallelism())),
      // One speech model at a time; the API unloads it when a file is done and
      // no dictation is open, and five idle minutes are the backstop.
      "--max-loaded-models",
      "1",
      "--idle-unload-ms",
      "300000",
      // A backstop behind the API's check against the model's measured peak.
      "--min-free-memory-mb",
      "1024",
      "--no-ui",
    ],
    // ggml loads its backend libraries from beside the executable.
    cwd: ctx.audioBinariesDir,
    // No eSpeak: only the voices phonemise.
    env: {},
  }
}
