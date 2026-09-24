/**
 * The Python sidecars: the API, and the worker once per queue. Same shape: a
 * frozen onedir binary when packaged, `uv run` in dev, same SURFSENSE_LOCAL_*
 * env. Both reach llama-server, so both need the bundled address.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { binaryPath as audiocppBinary, espeakPaths } from "./audiocpp.ts"
import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

function pythonEnv(ctx: SidecarContext): Record<string, string> {
  return {
    PYTHONUNBUFFERED: "1", // unbuffered: startup + crash logs show immediately
    SURFSENSE_LOCAL_HOST: ctx.host,
    SURFSENSE_LOCAL_PORT: String(ctx.apiPort),
    SURFSENSE_LOCAL_DATA_DIR: ctx.dataDir,
    SURFSENSE_LOCAL_SECRET: ctx.secret,
    ...(ctx.modelsDir && { SURFSENSE_LOCAL_MODELS_DIR: ctx.modelsDir }),
    ...(ctx.packaged && { HF_HUB_OFFLINE: "1" }),
    ...(ctx.llamacppUrl && { SURFSENSE_LOCAL_LLAMACPP_BASE_URL: ctx.llamacppUrl }),
    ...(ctx.llamacppModelsDir && {
      SURFSENSE_LOCAL_LLAMACPP_MODELS_DIR: ctx.llamacppModelsDir,
    }),
    // The API probes hardware by loading ggml from here. Without it the probe
    // runs from the wrong directory, finds no backends, and reports a CPU-only
    // machine with no error at all.
    ...(ctx.llamacppBinariesDir && {
      SURFSENSE_LOCAL_LLAMACPP_LIBRARY_DIR: ctx.llamacppBinariesDir,
    }),
    ...(ctx.imageUrl && { SURFSENSE_LOCAL_IMAGE_BASE_URL: ctx.imageUrl }),
    ...(ctx.imageModelsDir && {
      SURFSENSE_LOCAL_IMAGE_MODELS_DIR: ctx.imageModelsDir,
    }),
    // Only where audio.cpp is staged: without it the API offers no audio models,
    // and the Studio worker voices podcasts at the URL. The API names eSpeak in
    // server.json for Kitten, which does not read the server's environment.
    ...(ctx.audioModelsDir &&
      ctx.audioUrl &&
      ctx.audioBinariesDir &&
      existsSync(audiocppBinary(ctx)) && {
        SURFSENSE_LOCAL_AUDIO_MODELS_DIR: ctx.audioModelsDir,
        SURFSENSE_LOCAL_AUDIO_BASE_URL: ctx.audioUrl,
        SURFSENSE_LOCAL_AUDIO_ESPEAK_LIBRARY: espeakPaths(ctx.audioBinariesDir).library,
        SURFSENSE_LOCAL_AUDIO_ESPEAK_DATA: espeakPaths(ctx.audioBinariesDir).data,
      }),
  }
}

function pythonCmd(
  ctx: SidecarContext,
  name: string,
  devEntry: string,
  args: string[] = [],
): { cmd: string; args: string[]; cwd: string } {
  return ctx.packaged
    ? { cmd: join(ctx.binariesDir, "backend", name, exe(name)), args, cwd: ctx.binariesDir }
    : { cmd: "uv", args: ["run", devEntry, ...args], cwd: ctx.backendDir }
}

export function apiSpec(ctx: SidecarContext): SidecarSpec {
  return {
    name: "api",
    ...pythonCmd(ctx, "api", "main.py"),
    env: {
      ...pythonEnv(ctx),
      },
  }
}

export type WorkerQueue = "ingest" | "studio"

export function workerSpec(ctx: SidecarContext, queue: WorkerQueue): SidecarSpec {
  return {
    name: `worker-${queue}`,
    ...pythonCmd(ctx, "worker", "worker.py", [queue]),
    env: pythonEnv(ctx),
  }
}
