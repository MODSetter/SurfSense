/**
 * llama-server reads its per-model arguments from a preset INI **once, at
 * startup**: appending a section while it runs does not surface the model,
 * measured. The API rewrites that file whenever it installs a model or reprices
 * one, so the router has to be restarted to see it.
 *
 * Same shape as watchImageModel, and for the same reason: the API is the
 * authority, and a change is user-initiated and rare, so the few seconds of lag
 * cost nothing.
 */
import { join } from "node:path"

import { fileStamp } from "./file-stamp.ts"
import { LLAMACPP_SIDECAR, PRESET_FILE, llamacppSpec } from "./llamacpp.ts"
import type { WatcherOptions } from "./supervisor.ts"

// A poll, not a push: one local stat every few seconds, and no IPC channel.
const POLL_MS = 5000

/** Restart llama-server whenever the API rewrites its preset; returns the stop. */
export function watchGenerationPreset(options: WatcherOptions): () => void {
  const { ctx, control, stopping, pollMs = POLL_MS } = options
  if (ctx.llamacppModelsDir == null) return () => {}
  const preset = join(ctx.llamacppModelsDir, PRESET_FILE)
  let current = fileStamp(preset)

  const reconcile = async () => {
    if (stopping()) return
    const stamp = fileStamp(preset)
    if (stamp === current) return
    current = stamp

    if (control.running.has(LLAMACPP_SIDECAR)) await control.stop(LLAMACPP_SIDECAR)
    const spec = llamacppSpec(ctx)
    if (spec) control.start(spec)
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // Mid-write or mid-restart; the next tick tries again.
    })
  }, pollMs)
  timer.unref()
  return () => clearInterval(timer)
}