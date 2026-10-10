/**
 * audio.cpp's server refuses an empty model list, so it runs only while the
 * API's config names a model. The API rewrites that file on every audio install
 * and delete, and removes it with the last model; follow it, as for the preset.
 */
import { join } from "node:path"

import { AUDIOCPP_SIDECAR, SERVER_CONFIG, audiocppSpec } from "./audiocpp.ts"
import { fileStamp } from "./file-stamp.ts"
import type { WatcherOptions } from "./supervisor.ts"

const POLL_MS = 5000

/** Restart audiocpp whenever the API rewrites its model config; returns the stop. */
export function watchAudioModels(options: WatcherOptions): () => void {
  const { ctx, control, stopping, pollMs = POLL_MS } = options
  if (ctx.audioModelsDir == null) return () => {}
  const config = join(ctx.audioModelsDir, SERVER_CONFIG)
  let current = fileStamp(config)

  const reconcile = async () => {
    if (stopping()) return
    const stamp = fileStamp(config)
    if (stamp === current) return
    current = stamp

    if (control.running.has(AUDIOCPP_SIDECAR)) await control.stop(AUDIOCPP_SIDECAR)
    const spec = audiocppSpec(ctx)
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