import type { ReactElement } from "react"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { intl } from "@/i18n/intl"

import { useSpeechSetup } from "./use-speech-setup"

/**
 * Where speech recognition is needed but not set up, a waiting recording's row
 * and the composer's mic: it asks, then hands off to Settings, which alone
 * offers the models, their downloads and their progress.
 */
export function SpeechSetupPopover({
  trigger,
  open,
  onOpenChange,
  onStart,
  onMoreChoices,
  side = "top",
  align = "center",
}: {
  /** What opens it, such as the mic or a row's "Set up". */
  trigger: ReactElement
  open?: boolean
  onOpenChange?: (open: boolean) => void
  /** Present for the mic: once ready, it starts listening. */
  onStart?: () => void
  /** Opens Settings › Speech recognition, where the model is chosen. */
  onMoreChoices: () => void
  side?: "top" | "bottom" | "left" | "right"
  align?: "start" | "center" | "end"
}) {
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger render={trigger} />
      <PopoverContent side={side} align={align} className="w-80 gap-3 p-3">
        <SpeechSetupBody onStart={onStart} onMoreChoices={onMoreChoices} />
      </PopoverContent>
    </Popover>
  )
}

function SpeechSetupBody({
  onStart,
  onMoreChoices,
}: {
  onStart?: () => void
  onMoreChoices: () => void
}) {
  const setup = useSpeechSetup()

  if (setup.inUse) {
    return (
      <>
        <PopoverHeader>
          <PopoverTitle>
            {intl.formatMessage({
              id: "speech_setup_popover_ready_title",
              defaultMessage: "Speech recognition is ready",
            })}
          </PopoverTitle>
          <PopoverDescription>{setup.inUse.label}</PopoverDescription>
        </PopoverHeader>
        {onStart ? (
          <PopoverClose
            render={<Button type="button" size="sm" className="self-start" />}
            onClick={onStart}
          >
            {intl.formatMessage({
              id: "speech_setup_popover_start_button",
              defaultMessage: "Start talking",
            })}
          </PopoverClose>
        ) : (
          <PopoverClose
            render={
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="self-start"
              />
            }
          >
            {intl.formatMessage({
              id: "speech_setup_popover_done_button",
              defaultMessage: "Done",
            })}
          </PopoverClose>
        )}
      </>
    )
  }

  const downloading = setup.downloadPercent !== null
  return (
    <>
      <PopoverHeader>
        <PopoverTitle>
          {intl.formatMessage({
            id: "speech_setup_popover_title",
            defaultMessage: "Set up speech recognition",
          })}
        </PopoverTitle>
        <PopoverDescription>
          {downloading
            ? intl.formatMessage(
                {
                  id: "speech_setup_popover_downloading_body",
                  defaultMessage:
                    "Downloading the speech recognition model, {percent, number, ::percent}.",
                },
                { percent: (setup.downloadPercent ?? 0) / 100 }
              )
            : intl.formatMessage({
                id: "speech_setup_popover_ask_body",
                defaultMessage:
                  "Turn your voice into text, on this computer. Choose a model in Settings; it downloads once.",
              })}
        </PopoverDescription>
      </PopoverHeader>
      <div className="flex justify-end gap-2">
        {downloading ? null : (
          <PopoverClose
            render={<Button type="button" size="sm" variant="ghost" />}
          >
            {intl.formatMessage({
              id: "speech_setup_popover_not_now_button",
              defaultMessage: "Not now",
            })}
          </PopoverClose>
        )}
        <PopoverClose
          render={<Button type="button" size="sm" />}
          onClick={onMoreChoices}
        >
          {downloading
            ? intl.formatMessage({
                id: "speech_setup_popover_show_progress_button",
                defaultMessage: "Show progress",
              })
            : intl.formatMessage({
                id: "speech_setup_popover_set_up_button",
                defaultMessage: "Set up…",
              })}
        </PopoverClose>
      </div>
    </>
  )
}
