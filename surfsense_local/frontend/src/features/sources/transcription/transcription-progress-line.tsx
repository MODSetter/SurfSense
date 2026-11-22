import { Progress } from "@/components/ui/progress"
import { intl } from "@/i18n/intl"

import type { TranscriptionProgress } from "../api"
import { secondsLeft, type TranscriptionPace } from "./pace"

function transcribingText(
  progress: TranscriptionProgress,
  pace: TranscriptionPace | undefined
) {
  const total = Math.max(1, Math.round(progress.total_s / 60))
  const done = Math.min(Math.floor(progress.done_s / 60), total)
  const left = secondsLeft(pace, progress)
  if (left === null) {
    return intl.formatMessage(
      {
        id: "sources_row_transcribing_status",
        defaultMessage:
          "Transcribing · {done, number} of {total, number, ::unit/minute}",
      },
      { done, total }
    )
  }
  if (left < 60) {
    return intl.formatMessage(
      {
        id: "sources_row_transcribing_last_minute_status",
        defaultMessage:
          "Transcribing · {done, number} of {total, number, ::unit/minute} · less than a minute left",
      },
      { done, total }
    )
  }
  return intl.formatMessage(
    {
      id: "sources_row_transcribing_left_status",
      defaultMessage:
        "Transcribing · {done, number} of {total, number, ::unit/minute} · about {left, number, ::unit/minute} left",
    },
    { done, total, left: Math.round(left / 60) }
  )
}

/**
 * How much of a recording is transcribed: with a bar and the time left while
 * it runs, and as a share while it waits its turn after making way.
 */
export function TranscriptionProgressLine({
  progress,
  running,
  pace,
}: {
  progress: TranscriptionProgress
  running: boolean
  pace: TranscriptionPace | undefined
}) {
  const fraction =
    progress.total_s > 0 ? Math.min(1, progress.done_s / progress.total_s) : 0
  if (!running) {
    return (
      <p>
        {intl.formatMessage(
          {
            id: "sources_row_queued_status",
            defaultMessage:
              "Queued · {fraction, number, ::percent} transcribed",
          },
          { fraction }
        )}
      </p>
    )
  }
  return (
    <>
      <p>{transcribingText(progress, pace)}</p>
      {/* The sentence above says the same, so the bar is for the eye only. */}
      <Progress
        value={fraction * 100}
        aria-hidden
        className="w-full *:data-[slot=progress-track]:h-0.5"
      />
    </>
  )
}
