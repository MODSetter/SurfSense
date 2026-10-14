import { useAui } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { XIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Dictation } from "../dictation-adapter"
import type { DictationProblem } from "../dictation-problem"
import { isNotice, problemAction, problemText } from "./problem-text"

/** Why voice input stopped or could not start: one line, one action. */
export function ProblemLine({
  dictation,
  problem,
  canRetry,
  onOpenSpeechSettings,
  className,
}: {
  dictation: Dictation
  problem: DictationProblem
  canRetry: boolean
  onOpenSpeechSettings?: () => void
  className?: string
}) {
  const aui = useAui()
  const text = problemText(problem)
  const notice = isNotice(problem)
  const action = problemAction(problem, {
    canRetry,
    canSetUp: onOpenSpeechSettings !== undefined,
  })

  const act = () => {
    if (action === "open_settings") {
      void window.surfsense?.microphone?.openSettings()
    } else if (action === "retry") {
      dictation.retry(aui.composer())
    } else if (action === "try_again") {
      dictation.start(aui.composer())
    } else if (action === "set_up") {
      dictation.dismiss()
      onOpenSpeechSettings?.()
    }
  }

  const label =
    action === "open_settings"
      ? intl.formatMessage({
          id: "dictation_strip_open_settings_button",
          defaultMessage: "Open settings",
        })
      : action === "retry"
        ? intl.formatMessage({
            id: "dictation_strip_retry_button",
            defaultMessage: "Retry",
          })
        : action === "try_again"
          ? intl.formatMessage({
              id: "dictation_strip_try_again_button",
              defaultMessage: "Try again",
            })
          : intl.formatMessage({
              id: "dictation_strip_set_up_button",
              defaultMessage: "Set up",
            })

  return (
    <div
      className={cn("flex min-w-0 items-center gap-1.5 text-[11px]", className)}
    >
      <span
        role={notice ? "status" : "alert"}
        title={text}
        className={cn(
          "line-clamp-2 min-w-0 text-pretty",
          notice ? "text-muted-foreground" : "text-destructive"
        )}
      >
        {text}
      </span>
      {action === "dismiss" ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="shrink-0 text-muted-foreground"
          aria-label={intl.formatMessage({
            id: "dictation_strip_dismiss_aria",
            defaultMessage: "Dismiss",
          })}
          onClick={() => dictation.dismiss()}
        >
          <XIcon />
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="xs"
          className="shrink-0"
          onClick={act}
        >
          {label}
        </Button>
      )}
    </div>
  )
}
