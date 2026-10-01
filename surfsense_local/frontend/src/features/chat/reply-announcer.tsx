import { useEffect, useRef, useState } from "react"

import { intl } from "@/i18n/intl"

/**
 * A turn's one status region: "Thinking" until the answer starts, silent while
 * it streams, then that it finished. Feeding it every token would interrupt
 * a screen reader without pause, which is worse than saying nothing.
 */
export function ReplyAnnouncer({
  running,
  answerStarted,
}: {
  running: boolean
  answerStarted: boolean
}) {
  // Only a reply seen running finishes here: one loaded from history is not news.
  const sawRunning = useRef(running)
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    if (running) {
      sawRunning.current = true
    } else if (sawRunning.current && answerStarted) {
      setFinished(true)
    }
  }, [running, answerStarted])

  const text =
    running && !answerStarted
      ? intl.formatMessage({
          id: "chat_reasoning_thinking_label",
          defaultMessage: "Thinking",
        })
      : finished
        ? intl.formatMessage({
            id: "chat_reply_finished_status",
            defaultMessage: "Reply finished",
          })
        : ""

  return (
    <span role="status" className="sr-only">
      {text}
    </span>
  )
}
