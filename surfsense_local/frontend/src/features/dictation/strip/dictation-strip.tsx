import { useAui } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { XIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Dictation, DictationView } from "../dictation-adapter"
import { useDictationView } from "../use-dictation-view"
import { LevelBars } from "./level-bars"
import { ProblemLine } from "./problem-line"
import { RecordingTimer } from "./recording-timer"

type Status = { text: string; shown: boolean }

function statusOf(view: DictationView): Status | null {
  if (view.phase === "arming") {
    return {
      text: intl.formatMessage({
        id: "dictation_strip_arming_status",
        defaultMessage: "Starting the microphone…",
      }),
      shown: false,
    }
  }
  if (view.phase !== "listening" && view.phase !== "finishing") return null
  if (view.loading) {
    return {
      text: intl.formatMessage({
        id: "dictation_strip_loading_status",
        defaultMessage: "Loading the speech recognition model…",
      }),
      shown: true,
    }
  }
  if (view.phase === "finishing") {
    return {
      text: intl.formatMessage({
        id: "dictation_strip_transcribing_status",
        defaultMessage: "Transcribing…",
      }),
      shown: true,
    }
  }
  if (view.warning) {
    return {
      text: intl.formatMessage(
        {
          id: "dictation_strip_time_warning_status",
          defaultMessage:
            "Voice input stops in {seconds, plural, one {# second} other {# seconds}}.",
        },
        { seconds: 30 }
      ),
      shown: true,
    }
  }
  return {
    text: intl.formatMessage({
      id: "dictation_strip_listening_status",
      defaultMessage: "Listening",
    }),
    shown: false,
  }
}

/**
 * Inside the composer while voice input runs, in place of the source count
 * and model (center) or the disclaimer (bottom): never above the composer,
 * where the model notice and the scroll button sit.
 */
export function DictationStrip({
  dictation,
  onOpenSpeechSettings,
  className,
}: {
  dictation: Dictation
  onOpenSpeechSettings?: () => void
  className?: string
}) {
  const aui = useAui()
  const view = useDictationView(dictation)

  if (view.phase === "idle") return null
  if (view.phase === "problem") {
    return (
      <ProblemLine
        dictation={dictation}
        problem={view.problem}
        canRetry={view.canRetry}
        onOpenSpeechSettings={onOpenSpeechSettings}
        className={className}
      />
    )
  }

  const status = statusOf(view)
  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-2 text-[11px] text-muted-foreground select-none",
        className
      )}
    >
      {view.phase === "finishing" ? (
        <Spinner role="presentation" aria-hidden="true" className="size-3.5" />
      ) : (
        <>
          <span
            aria-hidden="true"
            className={cn(
              "size-2 shrink-0 rounded-full",
              view.phase === "listening"
                ? "bg-destructive"
                : "bg-muted-foreground/40"
            )}
          />
          <LevelBars dictation={dictation} arming={view.phase === "arming"} />
        </>
      )}
      {view.phase === "listening" ? (
        <RecordingTimer since={view.since} />
      ) : null}
      <span role="status" className={status?.shown ? "truncate" : "sr-only"}>
        {status?.text}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        className="ml-auto shrink-0"
        aria-label={intl.formatMessage({
          id: "dictation_strip_cancel_aria",
          defaultMessage: "Cancel voice input",
        })}
        onClick={() => dictation.cancel(aui.composer())}
      >
        <XIcon />
      </Button>
    </div>
  )
}
