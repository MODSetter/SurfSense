/**
 * The Python sidecars: the API, and the worker once per queue. Same shape: one
 * frozen onedir binary when packaged, told its role by its first argument, the
 * backend's venv interpreter in dev, same SURFSENSE_LOCAL_* env. Both reach
 * llama-server, so both need the bundled address.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { binaryPath as audiocppBinary, espeakPaths } from "./audiocpp.ts"
import { exe, isWindows } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

/** Whether audio.cpp's server is staged; without it there are no voices and no speech recognition. */
function audiocppStaged(ctx: SidecarContext): boolean {
  return ctx.audioBinariesDir != null && existsSync(audiocppBinary(ctx))
}

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
      audiocppStaged(ctx) && {
        SURFSENSE_LOCAL_AUDIO_MODELS_DIR: ctx.audioModelsDir,
        SURFSENSE_LOCAL_AUDIO_BASE_URL: ctx.audioUrl,
        SURFSENSE_LOCAL_AUDIO_ESPEAK_LIBRARY: espeakPaths(ctx.audioBinariesDir).library,
        SURFSENSE_LOCAL_AUDIO_ESPEAK_DATA: espeakPaths(ctx.audioBinariesDir).data,
      }),
  }
}

/**
 * The frozen backend's executable. One binary carries both roles, so the API
 * and the worker share one copy of every library instead of two.
 */
export const BACKEND_BINARY = "surfsense-backend"

function pythonCmd(
  ctx: SidecarContext,
  role: "api" | "worker",
  devEntry: string,
  args: string[] = [],
): { cmd: string; args: string[]; cwd: string } {
  // Not `uv run`: Windows kills the app's children with it but not theirs, and
  // under uv Python is one of theirs, so a Ctrl-C left workers taking the next
  // session's jobs. predev's own `uv run` scripts have synced this venv.
  const venv = join(ctx.backendDir, ".venv", isWindows ? "Scripts" : "bin")
  return ctx.packaged
    ? {
        cmd: join(ctx.binariesDir, "backend", exe(BACKEND_BINARY)),
        args: [role, ...args],
        cwd: ctx.binariesDir,
      }
    : { cmd: join(venv, exe("python")), args: [devEntry, ...args], cwd: ctx.backendDir }
}

export function apiSpec(ctx: SidecarContext): SidecarSpec {
  return {
    name: "api",
    ...pythonCmd(ctx, "api", "main.py"),
    env: {
      ...pythonEnv(ctx),
      // The usage panel counts everything under this process as the app.
      SURFSENSE_LOCAL_SHELL_PID: String(process.pid),
      // The API alone talks to opencode; a worker's environment is where plugins start.
      ...(ctx.opencodeUrl &&
        ctx.opencodePassword && {
          SURFSENSE_LOCAL_OPENCODE_URL: ctx.opencodeUrl,
          SURFSENSE_LOCAL_OPENCODE_PASSWORD: ctx.opencodePassword,
        }),
      ...(ctx.opencodeProxyPort != null && {
        SURFSENSE_LOCAL_OPENCODE_PROXY_PORT: String(ctx.opencodeProxyPort),
      }),
      // The API alone checks it: only Electron may print the agent's Word previews.
      ...(ctx.docxSnapshotKey && { SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY: ctx.docxSnapshotKey }),
      // The API alone calls the speech recognition server; workers go through its gate.
      ...(ctx.transcriptionUrl &&
        audiocppStaged(ctx) && {
          SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL: ctx.transcriptionUrl,
        }),
    },
  }
}

// One worker per backend queue (`backend/shared/queue.py`): ingest reads and
// indexes, studio writes, plugins pulls links added from the web.
export const WORKER_QUEUES = ["ingest", "studio", "plugins"] as const
export type WorkerQueue = (typeof WORKER_QUEUES)[number]

export function workerSpec(ctx: SidecarContext, queue: WorkerQueue): SidecarSpec {
  return {
    name: `worker-${queue}`,
    ...pythonCmd(ctx, "worker", "worker.py", [queue]),
    env: pythonEnv(ctx),
  }
}
