/**
 * llama-server in router mode: the local generation runtime.
 *
 * One process owns the models directory and spawns a worker per loaded model,
 * which is why the supervisor's existing tree kill matters here. Unlike
 * sd-server it starts with no model at all, so it boots with the others: the
 * router runs happily against an empty directory and reports `role: router`.
 *
 * Runs in dev as well as packaged, and for the same reason the Python sidecars
 * do: only the path to the binary differs. The previous runtime was a system
 * daemon a developer happened to have running, so dev needed no wiring; this
 * one is a pinned build, and testing against a different one tests something
 * the app never ships.
 *
 * Per-model arguments do not come from the API at runtime. `POST /models/load`
 * accepts an `args` field and ignores it, measured, so the window and cache
 * precision the fit calculation chose are written to a preset INI that the
 * router reads **once at startup**. Changing a model's plan, or installing one,
 * therefore means rewriting that file and restarting this sidecar.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const LLAMACPP_SIDECAR = "llamacpp"

/** The preset file the API writes; the router reads it at startup. */
export const PRESET_FILE = "models.ini"

export function binaryPath(ctx: SidecarContext): string {
  return join(ctx.llamacppBinariesDir ?? "", exe("llama-server"))
}

/**
 * Null when the pinned build is not staged, which is the only condition that
 * matters: `pnpm build:llamacpp` fetches it, and `predev` runs that too.
 */
export function llamacppSpec(ctx: SidecarContext): SidecarSpec | null {
  if (
    ctx.llamacppPort == null ||
    ctx.llamacppModelsDir == null ||
    ctx.llamacppBinariesDir == null
  ) {
    return null
  }

  const binary = binaryPath(ctx)
  if (!existsSync(binary)) return null

  const directory = ctx.llamacppBinariesDir
  const preset = join(ctx.llamacppModelsDir, PRESET_FILE)

  const args = [
    "--models-dir",
    ctx.llamacppModelsDir,
    "--host",
    ctx.host,
    "--port",
    String(ctx.llamacppPort),
    // One model resident at a time. This app asks one question at a time, and
    // a second resident model is memory taken from the one being used.
    "--models-max",
    "1",
    // Without this a model self-evicted after roughly 30s idle, measured, which
    // turns the second question of a conversation into a reload.
    "--sleep-idle-seconds",
    "300",
    // The chat path never asks the router to load anything: the proxy calls
    // ensure_model_ready before forwarding, so a cold model loads on the request
    // that needs it. Asking as well was a check-then-act across a socket, and it
    // lost the race to the request already loading the model. This is the
    // upstream default; stated because chat is now correct only while it holds.
    "--models-autoload",
    // llama-server ships its own web UI, which we neither need nor want exposed.
    "--no-ui",
    "--jinja",
    // Routes <think> blocks to message.reasoning_content. Without it a thinking
    // model's trace enters the answer and citation rewriting corrupts it.
    "--reasoning-format",
    "deepseek",
  ]
  // Absent until the API has priced a model, and the router rejects a missing file.
  if (existsSync(preset)) args.push("--models-preset", preset)

  return {
    name: LLAMACPP_SIDECAR,
    cmd: binary,
    args,
    // ggml scans the running executable's own directory for backend libraries,
    // so this cwd is what lets it find them. Elsewhere it reports no devices,
    // silently, and every model would run on the CPU.
    cwd: directory,
    env: { LLAMA_CACHE: ctx.llamacppModelsDir },
  }
}
