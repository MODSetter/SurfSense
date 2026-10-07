import { useScrollLock } from "@assistant-ui/react"
import { useId, useLayoutEffect, useRef, useState } from "react"
import { Streamdown, defaultRehypePlugins } from "streamdown"

import { ChevronRightIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import {
  STREAMDOWN_LINK_SAFETY,
  streamdownPlugins,
  streamingStreamdownPlugins,
} from "@/features/studio/viewers/streamdown-config"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { ThinkingIndicator } from "./thinking-indicator"

export type ReplyReasoning = { text: string; durationMs: number | null }

/** Prompt tokens read so far, out of those the model had left to read. */
export type ReplyProgress = { processed: number; total: number }

// How coarsely the live region follows the figure: a polite region fed every
// update is noise.
const ANNOUNCED_STEP = 0.25

// Streamdown's default rehype pass is raw, sanitize, then harden with every
// link and image allowed. The trace is model output from the same stream as
// the answer, so it takes the answer's harden limits instead (message.tsx),
// the way the assistant-ui primitive builds them.
type RehypePluggable = (typeof defaultRehypePlugins)[string]
const [harden] = defaultRehypePlugins.harden as Extract<
  RehypePluggable,
  readonly unknown[]
>
const traceRehypePlugins: RehypePluggable[] = [
  defaultRehypePlugins.raw,
  defaultRehypePlugins.sanitize,
  [
    harden,
    {
      allowedLinkPrefixes: ["*"],
      allowedImagePrefixes: [],
      allowedProtocols: ["http", "https", "mailto"],
      allowDataImages: false,
    },
  ] as RehypePluggable,
]

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

/** What the model is doing before and while it answers: loading, reading, thinking, or done thinking. */
export function ReplyThinking({
  running,
  answerStarted,
  reasoning,
  progress = null,
  queue = null,
  preparing = null,
}: {
  running: boolean
  answerStarted: boolean
  reasoning: ReplyReasoning | null
  progress?: ReplyProgress | null
  // The reply's place in line for the local runtime, while it waits there.
  queue?: { position: number } | null
  // An agent turn's sources being put in its folder, before anything else.
  preparing?: number | null
}) {
  const status = replyStatus(running, answerStarted, reasoning)
  if (!status) {
    return null
  }
  return (
    <ReplyHeader
      status={status}
      reasoning={reasoning}
      read={status === "pending" ? readFraction(progress) : null}
      waiting={status === "pending" ? (queue?.position ?? null) : null}
      preparing={status === "pending" && preparing ? preparing : null}
    />
  )
}

function waitingLabel(position: number) {
  return intl.formatMessage(
    {
      id: "chat_reasoning_waiting_label",
      defaultMessage:
        "Waiting for another reply ({position, selectordinal, one {#st} two {#nd} few {#rd} other {#th}} in line)",
    },
    { position }
  )
}

/** The part of the prompt read, while there is a part still to read. */
function readFraction(progress: ReplyProgress | null) {
  if (!progress || progress.processed <= 0) return null
  if (progress.processed >= progress.total) return null
  return progress.processed / progress.total
}

function readingLabel(fraction: number) {
  return intl.formatMessage(
    {
      id: "chat_reasoning_reading_label",
      defaultMessage: "Reading {percent, number, ::percent}",
    },
    { percent: fraction }
  )
}

function preparingLabel(count: number) {
  return intl.formatMessage(
    {
      id: "chat_reasoning_preparing_label",
      defaultMessage:
        "Preparing {count, plural, one {# source} other {# sources}}…",
    },
    { count }
  )
}

function ReplyHeader({
  status,
  reasoning,
  read,
  waiting = null,
  preparing,
}: {
  status: ReplyStatus
  reasoning: ReplyReasoning | null
  // The fraction of the prompt read so far, or null with no figure to show.
  read: number | null
  // The place in line while the reply waits for the local runtime.
  waiting?: number | null
  // Sources being prepared, or null when none are.
  preparing: number | null
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

  const thinking = intl.formatMessage({
    id: "chat_reasoning_thinking_label",
    defaultMessage: "Thinking",
  })
  // Same header from send to answer: waiting, then thinking or reading, so
  // the indicator never restarts when the reply's turn comes.
  const label = !working
    ? doneLabel(reasoning?.durationMs ?? null)
    : waiting !== null
      ? waitingLabel(waiting)
      : preparing !== null
        ? preparingLabel(preparing)
        : read === null
          ? thinking
          : readingLabel(read)
  const announcedRead =
    read === null ? 0 : Math.floor(read / ANNOUNCED_STEP) * ANNOUNCED_STEP
  const announcement =
    waiting !== null
      ? waitingLabel(waiting)
      : preparing !== null
        ? preparingLabel(preparing)
        : announcedRead > 0
          ? readingLabel(announcedRead)
          : thinking

  return (
    <div className="mb-3 w-full">
      {/* Outside the button, whose contents screen readers flatten. */}
      <span role="status" className="sr-only">
        {working ? announcement : ""}
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
              viewportClassName="max-h-52 rounded-lg px-3 py-2 text-sm leading-6 wrap-break-word text-muted-foreground outline-none"
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
              {/* Default mode: the trace streams in, unlike a viewer's
                  finished artifact. */}
              <Streamdown
                plugins={
                  status === "thinking"
                    ? streamingStreamdownPlugins
                    : streamdownPlugins
                }
                rehypePlugins={traceRehypePlugins}
                linkSafety={STREAMDOWN_LINK_SAFETY}
              >
                {reasoning.text}
              </Streamdown>
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
