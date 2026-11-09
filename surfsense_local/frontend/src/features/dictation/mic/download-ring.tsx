import { DownloadRing } from "@/components/ui/download-ring"
import { useSpeechDownloadPercent } from "@/features/speech-setup/use-speech-download"

/** The app's download ring around the mic, while a speech model downloads. */
export function SpeechDownloadRing() {
  const percent = useSpeechDownloadPercent()
  if (percent === null) return null
  return (
    <DownloadRing
      percent={percent}
      className="pointer-events-none absolute inset-0 size-full"
    />
  )
}
