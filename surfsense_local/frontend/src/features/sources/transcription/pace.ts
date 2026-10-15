import type { TranscriptionProgress } from "../api"

type Sample = { done_s: number; at: number }

/** Where a running transcription was when first heard from, and when last. */
export type TranscriptionPace = { first: Sample; latest: Sample }

/** The pace once a window reports `done_s` at `at` (milliseconds). */
export function advancePace(
  pace: TranscriptionPace | undefined,
  done_s: number,
  at: number
): TranscriptionPace {
  // Going back means a run resumed from its checkpoint: its speed starts over.
  if (!pace || done_s < pace.latest.done_s) {
    return { first: { done_s, at }, latest: { done_s, at } }
  }
  return { first: pace.first, latest: { done_s, at } }
}

/** Seconds until the transcript is done at the speed so far; null before one is known. */
export function secondsLeft(
  pace: TranscriptionPace | undefined,
  progress: TranscriptionProgress
): number | null {
  if (!pace) return null
  const heard = pace.latest.done_s - pace.first.done_s
  const took = (pace.latest.at - pace.first.at) / 1000
  if (heard <= 0 || took <= 0) return null
  const remaining = Math.max(0, progress.total_s - progress.done_s)
  return (remaining * took) / heard
}
