import type { WorkspaceDocument } from "../api"
import { AwaitingSpeechLine } from "./awaiting-speech-line"
import type { TranscriptionPace } from "./pace"
import { SearchCaveatLine } from "./search-caveat-line"
import { TranscriptionProgressLine } from "./transcription-progress-line"

function isEnglish(language: string | null) {
  return language === "en" || language?.startsWith("en-") === true
}

/**
 * The line under a recording's name: how its transcript is coming along, what
 * it waits for, or how search reads it. Nothing for any other source.
 */
export function RecordingLine({
  id,
  document,
  pace,
  onOpenSpeechSettings,
}: {
  // What the row's aria-describedby names.
  id: string
  document: WorkspaceDocument
  pace: TranscriptionPace | undefined
  onOpenSpeechSettings?: () => void
}) {
  const transcription = document.transcription
  if (!transcription) return null
  const { progress } = transcription
  const running = document.status === "processing"
  // Pending with windows done: it made way for other sources mid-run.
  const yielded = document.status === "pending" && (progress?.done_s ?? 0) > 0
  const line = transcription.awaiting ? (
    <AwaitingSpeechLine onOpenSpeechSettings={onOpenSpeechSettings} />
  ) : progress && (running || yielded) ? (
    <TranscriptionProgressLine
      progress={progress}
      running={running}
      pace={pace}
    />
  ) : document.status === "ready" && !isEnglish(transcription.language) ? (
    <SearchCaveatLine language={transcription.language} />
  ) : null
  return (
    // Kept while empty, so the row's aria-describedby always names it.
    <div
      id={id}
      className="flex min-w-0 flex-col gap-1 pb-1.5 pl-8.5 text-xs text-muted-foreground empty:hidden"
    >
      {line}
    </div>
  )
}
