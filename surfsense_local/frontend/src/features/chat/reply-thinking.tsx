import { useScrollLock } from "@assistant-ui/react"
import { useId, useLayoutEffect, useRef, useState } from "react"

import { ChevronRightIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { ThinkingIndicator } from "./thinking-indicator"

export type ReplyReasoning = { text: string; durationMs: number | null }

// How close to the bottom still counts as reading the newest line.
const FOLLOW_SLACK_PX = 16

// The easing and lengths surfsense_web's trace header uses.
const EASE_OUT = "ease-[cubic-bezier(0.22,1,0.36,1)]"

// One header from send to answer, so the indicator and shimmer never remount
// between states; a new state is a new value here, not a new tree. Once a reply
// can hold several trace segments (tool calls), the header moves between them:
// then key one live slot, as surfsense_web's `LIVE_TURN_SEGMENT_KEY` does.
type ReplyStatus = "pending" | "thinking" | "done"

function replyStatus(
  running: boolean,
  answerStarted: boolean,
  reasoning: ReplyReasoning | null
): ReplyStatus | null {
  const working = running && !answerStarted
  if (!reasoning) {
    return working ? "pending" : null
  }
  return working && reasoning.durationMs === null ? "thinking" : "done"
}

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
  const status = replyStatus(running, answerStarted, reasoning)
  if (!status) {
    return null
  }
  return <ReplyHeader status={status} reasoning={reasoning} />
}

function ReplyHeader({
  status,
  reasoning,
}: {
  status: ReplyStatus
  reasoning: ReplyReasoning | null
}) {
  const working = status !== "done"
  // Open while the trace streams and folded once the answer starts, unless the
  // person has chosen for themselves.
  const [chosen, setChosen] = useState<boolean | null>(null)
  const open = reasoning !== null && (chosen ?? status === "thinking")
  const toggleId = useId()
  const traceId = useId()
  const traceRef = useRef<HTMLDivElement>(null)
  // Follows the newest line until the reader scrolls up to read, and again
  // once they scroll back down.
  const following = useRef(true)
  // Without it the chat's auto-scroll chases the sliding trace to the bottom,
  // moving the header out from under the click.
  const slideRef = useRef<HTMLDivElement>(null)
  const lockChatScroll = useScrollLock(slideRef, 300) // the slide's duration-300

  useLayoutEffect(() => {
    const trace = traceRef.current
    if (trace && following.current) {
      trace.scrollTop = trace.scrollHeight
    }
  }, [reasoning?.text, open])

  const label = working
    ? intl.formatMessage({
        id: "chat_reasoning_thinking_label",
        defaultMessage: "Thinking",
      })
    : doneLabel(reasoning?.durationMs ?? null)

  return (
    <div className="mb-3 w-full">
      {/* Outside the button, whose contents screen readers flatten. */}
      <span role="status" className="sr-only">
        {working ? label : ""}
      </span>
      {/* Disabled, not swapped for a plain element, until there is a trace to
          open: swapping would remount the header and restart its motion. */}
      <button
        type="button"
        id={toggleId}
        disabled={!reasoning}
        aria-expanded={reasoning ? open : undefined}
        aria-controls={reasoning ? traceId : undefined}
        onClick={() => {
          lockChatScroll()
          setChosen(!open)
        }}
        className="group/thinking flex h-8 max-w-full items-center gap-2.5 rounded-md text-sm text-muted-foreground transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none enabled:hover:text-foreground"
      >
        <HeaderLead active={working}>{label}</HeaderLead>
        {reasoning ? (
          <ChevronRightIcon
            aria-hidden
            className={cn(
              "size-4 shrink-0 opacity-0 transition-[rotate,opacity] duration-200 group-hover/thinking:opacity-100 group-focus-visible/thinking:opacity-100 motion-reduce:transition-none",
              EASE_OUT,
              open && "rotate-90"
            )}
          />
        ) : null}
      </button>
      {reasoning ? (
        // Stays mounted so it can slide shut; inert while folded so the
        // hidden trace is out of reach.
        <div
          ref={slideRef}
          className={cn(
            "grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
            open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          )}
          aria-hidden={!open}
          inert={!open}
        >
          <div className="min-h-0 overflow-hidden">
            <ScrollFade
              className="mt-2 rounded-lg border border-border/60 bg-muted/20 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50"
              viewportClassName="max-h-52 rounded-lg px-3 py-2 text-sm leading-6 wrap-break-word whitespace-pre-wrap text-muted-foreground outline-none"
              id={traceId}
              ref={traceRef}
              role="region"
              aria-labelledby={toggleId}
              aria-busy={status === "thinking"}
              // A scroll box a keyboard can reach, or its overflow is mouse-only;
              // its ring is on the wrapper, since the fade's mask would clip it.
              tabIndex={0}
              onScroll={(event) => {
                const trace = event.currentTarget
                following.current =
                  trace.scrollHeight - trace.scrollTop - trace.clientHeight <=
                  FOLLOW_SLACK_PX
              }}
            >
              {reasoning.text}
            </ScrollFade>
          </div>
        </div>
      ) : null}
    </div>
  )
}

/** The indicator and label; the indicator folds away and the label slides into its place once thinking ends. */
function HeaderLead({
  active,
  children,
}: {
  active: boolean
  children: string
}) {
  return (
    <span className="flex min-w-0 items-center">
      <span
        className={cn(
          "grid transition-[grid-template-columns,opacity] motion-reduce:transition-none",
          EASE_OUT,
          active
            ? "grid-cols-[1fr] opacity-100 duration-150"
            : "grid-cols-[0fr] opacity-0 duration-200"
        )}
      >
        <span className="min-w-0 overflow-hidden">
          <ThinkingIndicator className="mr-2.5" />
        </span>
      </span>
      <span
        className={cn(
          "truncate font-medium",
          active && "shimmer shimmer-duration-1800"
        )}
      >
        {children}
      </span>
    </span>
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
