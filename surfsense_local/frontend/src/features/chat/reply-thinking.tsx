import { useId, useLayoutEffect, useRef, useState } from "react"

import { ChevronRightIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

export type ReplyReasoning = { text: string; durationMs: number | null }

// How close to the bottom still counts as reading the newest line.
const FOLLOW_SLACK_PX = 16

/** What the model is doing before and while it answers: loading, thinking, or done thinking. */
export function ReplyThinking({
  running,
  answerStarted,
  reasoning,
}: {
  running: boolean
  answerStarted: boolean
  reasoning: ReplyReasoning | null
}) {
  if (reasoning) {
    return (
      <ThinkingBlock
        reasoning={reasoning}
        thinking={running && !answerStarted && reasoning.durationMs === null}
      />
    )
  }
  if (!running || answerStarted) {
    return null
  }
  return (
    <p
      role="status"
      className="text-sm leading-7 text-muted-foreground motion-safe:animate-pulse"
    >
      {intl.formatMessage({
        id: "chat_reply_pending_status",
        defaultMessage: "Thinking…",
      })}
    </p>
  )
}

function ThinkingBlock({
  reasoning,
  thinking,
}: {
  reasoning: ReplyReasoning
  thinking: boolean
}) {
  // Open while the trace streams and folded once the answer starts, unless the
  // person has chosen for themselves.
  const [chosen, setChosen] = useState<boolean | null>(null)
  const open = chosen ?? thinking
  const traceId = useId()
  const traceRef = useRef<HTMLDivElement>(null)
  // Follows the newest line until the reader scrolls up to read, and again
  // once they scroll back down.
  const following = useRef(true)

  useLayoutEffect(() => {
    const trace = traceRef.current
    if (trace && following.current) {
      trace.scrollTop = trace.scrollHeight
    }
  }, [reasoning.text, open])

  return (
    <div className="mb-2 w-full">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={traceId}
        onClick={() => setChosen(!open)}
        className="flex items-center gap-1 rounded-md text-sm leading-7 text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <span className={cn(thinking && "motion-safe:animate-pulse")}>
          {thinking
            ? intl.formatMessage({
                id: "chat_reasoning_thinking_label",
                defaultMessage: "Thinking…",
              })
            : doneLabel(reasoning.durationMs)}
        </span>
        <ChevronRightIcon
          aria-hidden
          className={cn(
            "size-3.5 transition-transform motion-reduce:transition-none",
            open && "rotate-90"
          )}
        />
      </button>
      {open ? (
        <div
          id={traceId}
          ref={traceRef}
          // A scroll box a keyboard can reach, or its overflow is mouse-only.
          tabIndex={0}
          onScroll={(event) => {
            const trace = event.currentTarget
            following.current =
              trace.scrollHeight - trace.scrollTop - trace.clientHeight <=
              FOLLOW_SLACK_PX
          }}
          className="mt-1 max-h-48 overflow-y-auto overscroll-contain rounded-sm border-l-2 border-border pl-3 text-sm leading-6 whitespace-pre-wrap text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {reasoning.text}
        </div>
      ) : null}
    </div>
  )
}

function doneLabel(durationMs: number | null) {
  if (durationMs === null) {
    return intl.formatMessage({
      id: "chat_reasoning_done_untimed_label",
      defaultMessage: "Thought",
    })
  }
  return intl.formatMessage(
    {
      id: "chat_reasoning_done_label",
      defaultMessage:
        "Thought for {seconds, plural, one {# second} other {# seconds}}",
    },
    { seconds: Math.max(1, Math.round(durationMs / 1000)) }
  )
}
