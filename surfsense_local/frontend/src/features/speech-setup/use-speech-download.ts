import { installView } from "@/features/models/local/chat/install-view"
import { isRunning, jobsFor } from "@/features/models/local/installs/job-state"
import { useInstalls } from "@/features/models/local/installs/use-installs"

/** How far a speech model's download has got, wherever it was started; null when none runs. */
export function useSpeechDownloadPercent(): number | null {
  const download = jobsFor(useInstalls().filter(isRunning), "speech_to_text")[0]
  return download ? installView(download.event).percent : null
}
