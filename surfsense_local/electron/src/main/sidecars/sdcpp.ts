/**
 * stable-diffusion.cpp's sd-server: local image generation. Packaged only, like
 * Ollama, and unlike Ollama it holds exactly one model, named by -m at startup
 * and never switchable at runtime. So the process follows the chosen model: the
 * API says which weights and which flags, and index.ts restarts it on a change.
 *
 * It serves POST /v1/images/generations, the route the image provider already
 * speaks, so the backend reaches it as an ordinary OpenAI-compatible endpoint.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const SDCPP_SIDECAR = "sdcpp"

/** The weights sd-server should be running, as the API sees it. */
export interface ImageRuntime {
  file: string | null
  args: string[]
}

export function binaryPath(ctx: SidecarContext): string {
  return join(ctx.binariesDir, "sdcpp", exe("sd-server"))
}

/** Null whenever sd-server cannot run: dev, an unbuilt host, or no model. */
export function sdcppSpec(
  ctx: SidecarContext,
  runtime: ImageRuntime
): SidecarSpec | null {
  if (!ctx.packaged || ctx.imagePort == null || ctx.imageModelsDir == null) {
    return null
  }
  if (runtime.file === null) return null

  const binary = binaryPath(ctx)
  const model = join(ctx.imageModelsDir, runtime.file)
  // No prebuilt binary for this host, or the weights are not downloaded yet.
  if (!existsSync(binary) || !existsSync(model)) return null

  return {
    name: SDCPP_SIDECAR,
    cmd: binary,
    args: [
      "-m",
      model,
      "--listen-port",
      String(ctx.imagePort),
      // Measured on the packaged build: 33s to first image, 3.5s after.
      "--diffusion-fa",
      ...runtime.args,
    ],
    cwd: join(ctx.binariesDir, "sdcpp"),
    env: {},
  }
}
