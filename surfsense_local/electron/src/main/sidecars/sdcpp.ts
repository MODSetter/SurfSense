/**
 * stable-diffusion.cpp's sd-server: local image generation. Runs in dev and
 * packaged, like llama-server, and unlike it this holds exactly one model,
 * named by its files at startup and never switchable at runtime. So the
 * process follows the chosen model: the API says which files and which flags,
 * and index.ts restarts it on a change.
 *
 * It serves POST /v1/images/generations, the route the image provider already
 * speaks, so the backend reaches it as an ordinary OpenAI-compatible endpoint.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const SDCPP_SIDECAR = "sdcpp"

/** What sd-server should be running, as the API sees it: each file of the
 * build on the flag that names it, inside the images folder. */
export interface ImageRuntime {
  files: { flag: string; path: string }[]
  args: string[]
}

export function binaryPath(ctx: SidecarContext): string {
  return join(ctx.sdcppBinariesDir ?? "", exe("sd-server"))
}

/** Null whenever sd-server cannot run: an unbuilt host, or no model. */
export function sdcppSpec(
  ctx: SidecarContext,
  runtime: ImageRuntime
): SidecarSpec | null {
  if (
    ctx.imagePort == null ||
    ctx.imageModelsDir == null ||
    ctx.sdcppBinariesDir == null
  ) {
    return null
  }
  if (runtime.files.length === 0) return null

  const binary = binaryPath(ctx)
  const imageModelsDir = ctx.imageModelsDir
  const files = runtime.files.map(({ flag, path }) => [flag, join(imageModelsDir, path)])
  // No staged binary on this host, or a file of the build is not on disk yet.
  if (!existsSync(binary) || files.some(([, path]) => !existsSync(path))) return null

  return {
    name: SDCPP_SIDECAR,
    cmd: binary,
    args: [
      ...files.flat(),
      "--listen-port",
      String(ctx.imagePort),
      // Measured on the packaged build: 33s to first image, 3.5s after.
      "--diffusion-fa",
      ...runtime.args,
    ],
    cwd: ctx.sdcppBinariesDir,
    env: {},
  }
}
