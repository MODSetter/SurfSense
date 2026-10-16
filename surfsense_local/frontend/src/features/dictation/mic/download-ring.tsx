import { installView } from "@/features/models/local/chat/install-view"
import { isRunning, jobsFor } from "@/features/models/local/installs/job-state"
import { useInstalls } from "@/features/models/local/installs/use-installs"

const RADIUS = 16
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** How far a speech model's download got, around the mic while it runs. */
export function DownloadRing() {
  const download = jobsFor(useInstalls().filter(isRunning), "speech_to_text")[0]
  const percent = download ? installView(download.event).percent : null
  if (percent === null) return null
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 36 36"
      className="pointer-events-none absolute inset-0 size-full -rotate-90"
    >
      <circle
        cx="18"
        cy="18"
        r={RADIUS}
        fill="none"
        strokeWidth="2"
        className="stroke-primary transition-[stroke-dashoffset] duration-300 motion-reduce:transition-none"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={CIRCUMFERENCE * (1 - percent / 100)}
        strokeLinecap="round"
      />
    </svg>
  )
}
