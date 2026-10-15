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
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { SpeechModelCard } from "./speech-model-card"
import { useSpeechSetup } from "./use-speech-setup"

/**
 * Setting up speech recognition where it is needed: a waiting recording's row
 * and the composer's mic. Downloading also chooses the model, so one click
 * is the whole set-up; Settings holds every other choice.
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
  /** Opens Settings › Speech recognition. */
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

  const { catalog } = setup
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
          {intl.formatMessage({
            id: "speech_setup_popover_body",
            defaultMessage:
              "SurfSense turns your voice into text on this computer. It needs a one-time download.",
          })}
        </PopoverDescription>
      </PopoverHeader>

      {catalog.isPending ? (
        <Spinner className="self-center" />
      ) : catalog.isError ? (
        <p className="text-destructive">
          {intl.formatMessage({
            id: "speech_setup_popover_load_error",
            defaultMessage: "Could not load speech recognition models.",
          })}
        </p>
      ) : setup.curated.length === 0 ? (
        <p className="text-muted-foreground">
          {intl.formatMessage({
            id: "speech_setup_popover_unsupported_body",
            defaultMessage: "Speech recognition can’t run on this computer.",
          })}
        </p>
      ) : (
        setup.curated.map((model) => (
          <SpeechModelCard
            key={model.id}
            model={model}
            download={setup.downloadOf(model)}
            busy={setup.choosing || setup.settling(model)}
            onSetUp={() => setup.setUp(model)}
            onCancel={setup.cancel}
          />
        ))
      )}

      {setup.chooseError ? (
        <p className="text-destructive">{setup.chooseError.message}</p>
      ) : null}

      {catalog.isSuccess && setup.curated.length > 0 ? (
        <PopoverClose
          render={
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="-ml-2 self-start text-muted-foreground"
            />
          }
          onClick={onMoreChoices}
        >
          {intl.formatMessage({
            id: "speech_setup_popover_more_button",
            defaultMessage: "More choices",
          })}
        </PopoverClose>
      ) : null}
    </>
  )
}
