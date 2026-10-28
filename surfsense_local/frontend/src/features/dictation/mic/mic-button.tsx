import { useState } from "react"
import { useAui } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { Mic01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { SpeechSetupPopover } from "@/features/speech-setup/speech-setup-popover"
import { useSpeechDownloadPercent } from "@/features/speech-setup/use-speech-download"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Dictation } from "../dictation-adapter"
import { useProblemToasts } from "../problem-toasts"
import { isLasting, problemText } from "../strip/problem-text"
import { isRecording, useDictationView } from "../use-dictation-view"
import { useNeedsSpeechModel } from "../use-transcription-status"
import { SpeechDownloadRing } from "./download-ring"

/**
 * Voice input, beside Send. A click, or Space or Enter on it, starts it; it
 * hides while recording, when Stop and insert or Enter in the box stops it.
 * With no speech model yet it sets one up instead. No push to talk: holding a
 * button that hides as it starts is no way to talk.
 */
export function MicButton({
  dictation,
  disabled,
  onOpenSpeechSettings,
  className,
}: {
  dictation: Dictation
  /** Whenever the message box is, and once it is at its limit. */
  disabled: boolean
  onOpenSpeechSettings?: () => void
  className?: string
}) {
  const aui = useAui()
  const view = useDictationView(dictation)
  const needsModel = useNeedsSpeechModel()
  const [setUpOpen, setSetUpOpen] = useState(false)
  const active = isRecording(view)
  const start = () => dictation.start(aui.composer())
  useProblemToasts(dictation, onOpenSpeechSettings)
  const downloadPercent = useSpeechDownloadPercent()
  // No microphone, or no secure page: true until something outside changes.
  const lasting =
    view.phase === "problem" && isLasting(view.problem) ? view.problem : null
  const tooltip = lasting
    ? problemText(lasting)
    : downloadPercent !== null
      ? intl.formatMessage(
          {
            id: "dictation_mic_downloading_tooltip",
            defaultMessage:
              "Downloading the speech recognition model, {percent, number, ::percent}",
          },
          { percent: downloadPercent / 100 }
        )
      : intl.formatMessage({
          id: "dictation_mic_idle_tooltip",
          defaultMessage: "Voice input stays on this computer",
        })

  // A recording is always stopped from the mic; an open set-up stays until it
  // is closed, even once its model is chosen.
  if ((needsModel && !active) || setUpOpen) {
    return (
      <Tooltip>
        <SpeechSetupPopover
          open={setUpOpen}
          onOpenChange={setSetUpOpen}
          align="end"
          onStart={start}
          onMoreChoices={onOpenSpeechSettings ?? (() => undefined)}
          trigger={
            <TooltipTrigger
              render={
                <Button
                  type="button"
                  size="icon-lg"
                  variant="ghost"
                  disabled={disabled}
                  className={cn("relative rounded-xl", className)}
                  aria-label={intl.formatMessage({
                    id: "dictation_mic_set_up_aria",
                    defaultMessage: "Set up voice input",
                  })}
                >
                  <Mic01Icon className="size-5" />
                  <SpeechDownloadRing />
                </Button>
              }
            />
          }
        />
        <TooltipContent side="top">{tooltip}</TooltipContent>
      </Tooltip>
    )
  }

  // Starting: a spinner where the mic was, so the click shows it was heard.
  if (view.phase === "arming") {
    return (
      <Button
        type="button"
        size="icon-lg"
        variant="ghost"
        disabled
        className={cn("rounded-xl disabled:opacity-100", className)}
        aria-label={intl.formatMessage({
          id: "dictation_mic_starting_aria",
          defaultMessage: "Starting the microphone…",
        })}
      >
        <Spinner className="size-5" />
      </Button>
    )
  }

  // While it records, the strip and Send's place, now Stop and insert, hold
  // the controls.
  if (active) return null

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            size="icon-lg"
            variant="ghost"
            disabled={disabled}
            aria-label={intl.formatMessage({
              id: "dictation_mic_start_aria",
              defaultMessage: "Start voice input",
            })}
            className={cn("relative rounded-xl", className)}
            // The message box keeps the focus, so Enter and Escape reach it.
            onMouseDown={(event) => event.preventDefault()}
            onClick={(event) => {
              // The mic is about to hide: the message box takes the focus,
              // where Enter stops and Escape cancels.
              event.currentTarget
                .closest("form")
                ?.querySelector("textarea")
                ?.focus()
              start()
            }}
          >
            <Mic01Icon className="size-5" />
            {lasting ? (
              <span
                aria-hidden="true"
                className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-destructive"
              />
            ) : null}
          </Button>
        }
      />
      <TooltipContent side="top">{tooltip}</TooltipContent>
    </Tooltip>
  )
}
