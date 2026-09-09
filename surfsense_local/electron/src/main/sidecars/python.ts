/**
 * The two Python sidecars. They are the same shape: a frozen onedir binary in
 * the packaged app, `uv run` in dev, over the same SURFSENSE_LOCAL_* env. Chat
 * hits Ollama from the API; Studio generation hits it from the worker — both
 * need the bundled address.
 */
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

function pythonEnv(ctx: SidecarContext): Record<string, string> {
  return {
    PYTHONUNBUFFERED: "1", // unbuffered: startup + crash logs show immediately
    SURFSENSE_LOCAL_HOST: ctx.host,
    SURFSENSE_LOCAL_PORT: String(ctx.apiPort),
    SURFSENSE_LOCAL_DATA_DIR: ctx.dataDir,
    ...(ctx.modelsDir && { SURFSENSE_LOCAL_MODELS_DIR: ctx.modelsDir }),
    ...(ctx.packaged && { HF_HUB_OFFLINE: "1" }),
    ...(ctx.ollamaUrl && { SURFSENSE_LOCAL_OLLAMA_BASE_URL: ctx.ollamaUrl }),
    ...(ctx.ollamaModelsDir && {
      SURFSENSE_LOCAL_OLLAMA_MODELS_DIR: ctx.ollamaModelsDir,
    }),
  }
}

function pythonCmd(
  ctx: SidecarContext,
  name: string,
  devEntry: string,
): { cmd: string; args: string[]; cwd: string } {
  return ctx.packaged
    ? { cmd: join(ctx.binariesDir, "backend", name, exe(name)), args: [], cwd: ctx.binariesDir }
    : { cmd: "uv", args: ["run", devEntry], cwd: ctx.backendDir }
}

export function apiSpec(ctx: SidecarContext): SidecarSpec {
  return {
    name: "api",
    ...pythonCmd(ctx, "api", "main.py"),
    env: {
      ...pythonEnv(ctx),
      ...(ctx.llmfitPath && { SURFSENSE_LOCAL_LLMFIT_PATH: ctx.llmfitPath }),
    },
  }
}

export function workerSpec(ctx: SidecarContext): SidecarSpec {
  return {
    name: "worker",
    ...pythonCmd(ctx, "worker", "worker.py"),
    env: pythonEnv(ctx),
  }
}
