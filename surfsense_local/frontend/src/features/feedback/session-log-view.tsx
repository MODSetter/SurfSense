import { useId, useLayoutEffect, useRef } from "react"

import { Button } from "@/components/ui/button"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { useCopyToClipboard } from "@/features/about/use-copy-to-clipboard"
import { intl } from "@/i18n/intl"

// Scrolled this close to the end, the reader is following new lines, not reading old ones.
const FOLLOW_SLACK_PX = 24

export function SessionLogView({ lines }: { lines: string[] }) {
  const titleId = useId()
  const text = lines.join("\n")
  const { copied, copy } = useCopyToClipboard(text)
  const logRef = useRef<HTMLDivElement>(null)
  const following = useRef(true)

  useLayoutEffect(() => {
    const log = logRef.current
    if (log && following.current) log.scrollTop = log.scrollHeight
  }, [text])

  return (
    <section className="flex min-w-0 flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 id={titleId} className="text-sm font-medium">
          {intl.formatMessage({
            id: "feedback_log_title",
            defaultMessage: "Session log",
          })}
        </h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={lines.length === 0}
          onClick={() => void copy()}
        >
          {copied ? (
            <CheckIcon data-icon="inline-start" />
          ) : (
            <CopyIcon data-icon="inline-start" />
          )}
          {copied
            ? intl.formatMessage({
                id: "feedback_log_copied_button",
                defaultMessage: "Copied",
              })
            : intl.formatMessage({
                id: "feedback_log_copy_button",
                defaultMessage: "Copy log",
              })}
        </Button>
      </div>
      {/* Polled every second, so a live region would read each new line aloud.
          The ring sits on the wrapper: the fade's mask would clip it. */}
      <ScrollFade
        className="rounded-lg bg-muted has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50"
        viewportClassName="h-56 max-h-[30vh] p-3 outline-none"
        ref={logRef}
        role="log"
        aria-labelledby={titleId}
        aria-live="off"
        tabIndex={0}
        onScroll={(event) => {
          const log = event.currentTarget
          following.current =
            log.scrollHeight - log.scrollTop - log.clientHeight <=
            FOLLOW_SLACK_PX
        }}
      >
        <pre className="font-mono text-xs leading-relaxed wrap-anywhere whitespace-pre-wrap select-text">
          {lines.length > 0
            ? text
            : intl.formatMessage({
                id: "feedback_log_empty",
                defaultMessage: "Nothing logged yet",
              })}
        </pre>
      </ScrollFade>
    </section>
  )
}
