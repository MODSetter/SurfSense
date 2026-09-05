/**
 * The two Python sidecars. They are the same shape: a frozen onedir binary in
 * the packaged app, `uv run` in dev, over the same SURFSENSE_LOCAL_* env. Only
 * the API talks to Ollama, so only it gets the base URL.
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
    ...(ctx.hfHome && { HF_HOME: ctx.hfHome }),
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
      // chat generation reaches the bundled Ollama (packaged only)
      ...(ctx.ollamaUrl && { SURFSENSE_LOCAL_OLLAMA_BASE_URL: ctx.ollamaUrl }),
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
