import { installView } from "@/features/models/local/chat/install-view"
import { cancelInstall } from "@/features/models/local/installs/api"
import { isRunning, jobsFor } from "@/features/models/local/installs/job-state"
import { useInstalls } from "@/features/models/local/installs/use-installs"

/** A speech model's download under way, wherever it was started; null when none runs. */
export function useSpeechDownload(): {
  percent: number | null
  cancel: () => void
} | null {
  const download = jobsFor(useInstalls().filter(isRunning), "speech_to_text")[0]
  if (!download) return null
  return {
    percent: installView(download.event).percent,
    // A 404 means it already ended, which the feed reports.
    cancel: () => void cancelInstall(download.id).catch(() => undefined),
  }
}

/** How far that download has got, for the mic's ring and tooltip. */
export function useSpeechDownloadPercent(): number | null {
  return useSpeechDownload()?.percent ?? null
}
