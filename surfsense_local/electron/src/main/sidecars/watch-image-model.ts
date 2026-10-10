/**
 * sd-server takes its model as a startup argument and dies without one, so it
 * cannot be started at boot like the others: the model arrives later, on a
 * download, and changes again whenever a different one is chosen. The API is the
 * authority on which weights that is, so follow it and restart on a change.
 *
 * A poll, not a push. It costs one local request every few seconds and needs no
 * IPC channel of its own; a change is user-initiated and rare, so the few
 * seconds of lag are not felt.
 */
import type { WatcherOptions } from "./supervisor.ts"
import { SDCPP_SIDECAR, sdcppSpec, type ImageRuntime } from "./sdcpp.ts"

const POLL_MS = 5000

/** Start, restart or stop sd-server for the chosen image model; returns the stop. */
export function watchImageModel(options: WatcherOptions): () => void {
  const { ctx, control, stopping, pollMs = POLL_MS } = options
  if (ctx.imageModelsDir == null) return () => {}
  const endpoint = `http://${ctx.host}:${ctx.apiPort}/llm/image/local/runtime`
  let current: string | null = null

  const reconcile = async () => {
    if (stopping()) return
    const response = await fetch(endpoint)
    if (!response.ok) return
    const runtime = (await response.json()) as ImageRuntime

    const spec = sdcppSpec(ctx, runtime)
    const wanted = spec ? spec.args.join("\u0000") : null
    if (wanted === current) return

    if (control.running.has(SDCPP_SIDECAR)) await control.stop(SDCPP_SIDECAR)
    current = wanted
    if (spec) control.start(spec)
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // The API is down or restarting; the next tick tries again.
    })
  }, pollMs)
  timer.unref()
  return () => clearInterval(timer)
}