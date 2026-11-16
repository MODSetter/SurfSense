/**
 * The speech recognition server runs while the API's transcription.json names
 * a model: started when it appears, restarted when it changes, stopped when it
 * goes. Unlike the voices' server it comes back after a crash, since a
 * recording or a dictation waits on it, but not forever.
 */
import type { ChildProcess } from "node:child_process"
import { join } from "node:path"

import { sessionLog } from "./session-log/session-log.ts"
import { warnMain } from "./session-log/main-warn.ts"
import {
  AUDIOCPP_TRANSCRIPTION_SIDECAR,
  TRANSCRIPTION_CONFIG,
  audiocppTranscriptionSpec,
} from "./audiocpp-transcription.ts"
import { fileStamp } from "./file-stamp.ts"
import type { WatcherOptions } from "./supervisor.ts"

const POLL_MS = 5000
// As opencode's: a server that dies at once is not restarted in a tight loop.
const RESTART_MS = 10_000
// Past this, it is left stopped and the API reports transcription_unavailable;
// a new config, as when another speech model is chosen, tries again.
const CRASH_LIMIT = 3
const CRASH_WINDOW_MS = 5 * 60_000

export interface TranscriptionWatcherOptions extends WatcherOptions {
  /** The clock restarts are spaced and crashes counted on; a test moves it. */
  now?: () => number
}

/** Follow the API's speech model config and restart the server after a crash; returns the stop. */
export function watchTranscriptionModels(options: TranscriptionWatcherOptions): () => void {
  const { ctx, control, stopping, pollMs = POLL_MS, now = Date.now } = options
  if (ctx.audioModelsDir == null) return () => {}
  const config = join(ctx.audioModelsDir, TRANSCRIPTION_CONFIG)
  let current = fileStamp(config)
  let lastStart = now()
  let crashes: number[] = []
  let counted: ChildProcess | undefined
  let gaveUp = false

  const start = () => {
    // Checked again after a stop: the quit stops only what runs when it begins.
    if (stopping()) return
    const spec = audiocppTranscriptionSpec(ctx)
    if (!spec) return
    control.start(spec)
    lastStart = now()
  }

  /** Count a crash once per child; true once the server has crashed too often to restart. */
  const tooManyCrashes = (child: ChildProcess): boolean => {
    if (child === counted) return gaveUp
    counted = child
    const at = now()
    crashes = [...crashes.filter((t) => at - t < CRASH_WINDOW_MS), at]
    if (crashes.length >= CRASH_LIMIT) {
      gaveUp = true
      warnMain(
        sessionLog,
        `${AUDIOCPP_TRANSCRIPTION_SIDECAR} crashed ${CRASH_LIMIT} times in 5 minutes; not restarting it`
      )
    }
    return gaveUp
  }

  /** Restart on a config change, or after a crash while the budget allows. */
  const reconcile = async () => {
    if (stopping()) return
    const stamp = fileStamp(config)
    if (stamp !== current) {
      current = stamp
      crashes = []
      gaveUp = false
      if (control.running.has(AUDIOCPP_TRANSCRIPTION_SIDECAR)) {
        await control.stop(AUDIOCPP_TRANSCRIPTION_SIDECAR)
      }
      start()
      return
    }

    const child = control.running.get(AUDIOCPP_TRANSCRIPTION_SIDECAR)
    if (child == null || (child.exitCode === null && child.signalCode === null)) return
    if (tooManyCrashes(child)) return
    if (now() - lastStart < RESTART_MS) return
    start()
  }

  // A tick during a slow stop would start a second server over the first.
  let reconciling = false
  const timer = setInterval(() => {
    if (reconciling) return
    reconciling = true
    void reconcile()
      .catch(() => {
        // Mid-write or mid-restart; the next tick tries again.
      })
      .finally(() => {
        reconciling = false
      })
  }, pollMs)
  timer.unref()
  return () => clearInterval(timer)
}
