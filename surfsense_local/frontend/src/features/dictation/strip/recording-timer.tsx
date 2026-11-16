import { useEffect, useState } from "react"

import { intl } from "@/i18n/intl"

/** Minutes and seconds since the first real frame. */
export function RecordingTimer({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(tick)
  }, [])

  const elapsed = Math.max(0, Math.floor((now - since) / 1000))
  return (
    <span className="shrink-0 tabular-nums">
      {intl.formatMessage(
        {
          id: "dictation_strip_timer_label",
          defaultMessage:
            "{minutes, number}:{seconds, number, ::integer-width/*00}",
        },
        { minutes: Math.floor(elapsed / 60), seconds: elapsed % 60 }
      )}
    </span>
  )
}
