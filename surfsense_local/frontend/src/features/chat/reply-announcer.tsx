import { useEffect, useRef, useState } from "react"

import { intl } from "@/i18n/intl"

/**
 * Says once that a reply finished. The thinking header's own status region
 * covers the wait; this one stays silent while the answer streams, since
 * feeding it every token would interrupt a screen reader without pause.
 */
export function ReplyAnnouncer({
  running,
  answerStarted,
  completed,
}: {
  running: boolean
  answerStarted: boolean
  // False for a reply that failed or was stopped: its alert, not this, says so.
  completed: boolean
}) {
  // Only a reply seen running finishes here: one loaded from history is not news.
  const sawRunning = useRef(running)
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    if (running) {
      sawRunning.current = true
    } else if (sawRunning.current && answerStarted && completed) {
      setFinished(true)
    }
  }, [running, answerStarted, completed])

  // Mounted empty and filled only later, so the region exists before it speaks.
  return (
    <span role="status" className="sr-only">
      {finished
        ? intl.formatMessage({
            id: "chat_reply_finished_status",
            defaultMessage: "Reply finished",
          })
        : ""}
    </span>
  )
}
