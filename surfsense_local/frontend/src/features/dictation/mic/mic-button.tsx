import { useRef, useState, type PointerEvent } from "react"
import { useAui } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { Mic01Icon } from "@/components/ui/icons"
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

// Handy's hold-or-toggle: a press held this long is push to talk.
const HOLD_MS = 300

/**
 * Voice input, beside Send. A click toggles it, a hold talks until release,
 * and Space or Enter on the focused mic toggles it; with no speech model yet
 * it sets one up instead.
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
  // The pointer press under way: whether it started the recording, and when.
  const press = useRef<{ startedIt: boolean; at: number } | null>(null)
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

  const pressed = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return
    if (view.phase === "finishing") return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    press.current = { startedIt: !active, at: performance.now() }
    if (!active) start()
  }

  const released = () => {
    const held = press.current
    press.current = null
    if (!held) return
    // A tap that started it keeps listening; a hold, or a tap while it listens, stops.
    if (!held.startedIt || performance.now() - held.at >= HOLD_MS) {
      dictation.stop()
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            size="icon-lg"
            variant="ghost"
            disabled={disabled && !active}
            aria-pressed={active}
            aria-label={
              active
                ? intl.formatMessage({
                    id: "dictation_mic_stop_aria",
                    defaultMessage: "Stop voice input",
                  })
                : intl.formatMessage({
                    id: "dictation_mic_start_aria",
                    defaultMessage: "Start voice input",
                  })
            }
            className={cn(
              "relative rounded-xl",
              active && "bg-muted text-destructive hover:text-destructive",
              className
            )}
            // The message box keeps the focus, so Enter and Escape reach it.
            onMouseDown={(event) => event.preventDefault()}
            onPointerDown={pressed}
            onPointerUp={released}
            onPointerCancel={released}
            onClick={(event) => {
              // Pointers act on down and up; this is Space or Enter on the mic.
              if (event.detail !== 0) return
              if (active) dictation.stop()
              else start()
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape" && active) {
                event.preventDefault()
                dictation.cancel(aui.composer())
              }
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
