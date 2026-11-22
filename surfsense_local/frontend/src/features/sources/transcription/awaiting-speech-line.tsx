import { Button } from "@/components/ui/button"
import { SpeechSetupPopover } from "@/features/speech-setup/speech-setup-popover"
import { intl } from "@/i18n/intl"

/**
 * A recording added before any speech recognition model: a wait, not a
 * failure. Choosing a model queues it again, so set-up is the whole fix.
 */
export function AwaitingSpeechLine({
  setUpOpen,
  onSetUpOpenChange,
  onOpenSpeechSettings,
}: {
  setUpOpen: boolean
  onSetUpOpenChange: (open: boolean) => void
  // Absent, the line only says what it waits for.
  onOpenSpeechSettings?: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-2">
      <span>
        {intl.formatMessage({
          id: "sources_row_awaiting_speech_status",
          defaultMessage: "Waiting for speech recognition",
        })}
      </span>
      {onOpenSpeechSettings ? (
        <SpeechSetupPopover
          open={setUpOpen}
          onOpenChange={onSetUpOpenChange}
          side="right"
          align="start"
          onMoreChoices={onOpenSpeechSettings}
          trigger={
            <Button
              type="button"
              variant="link"
              size="xs"
              className="h-auto px-0 text-xs"
            >
              {intl.formatMessage({
                id: "sources_row_awaiting_speech_button",
                defaultMessage: "Set up",
              })}
            </Button>
          }
        />
      ) : null}
    </div>
  )
}
