import { useId } from "react"

import { Button } from "@/components/ui/button"
import { DownloadIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { InstallProgress } from "@/features/models/local/chat/install-progress"
import type { InstallJob } from "@/features/models/local/installs/api"
import type { LocalSpeechModel } from "@/features/models/local/transcription/api"
import { speechModelSize } from "@/features/models/local/transcription/describe-speech-model"
import { listLanguages } from "@/features/models/local/transcription/language-names"
import { intl } from "@/i18n/intl"

/** One curated model: what it downloads and where it works well. */
export function SpeechModelCard({
  model,
  download,
  busy,
  onSetUp,
  onCancel,
}: {
  model: LocalSpeechModel
  /** This model's download, while it runs. */
  download: InstallJob | null
  busy: boolean
  onSetUp: () => void
  onCancel: (jobId: string) => void
}) {
  const nameId = useId()

  return (
    <div
      role="group"
      aria-labelledby={nameId}
      className="flex flex-col gap-2 rounded-lg border px-3 py-2.5"
    >
      <div className="flex flex-col gap-0.5">
        <p id={nameId} className="text-sm font-medium">
          {model.label}
        </p>
        <p className="text-xs text-muted-foreground tabular-nums">
          {speechModelSize(model)}
        </p>
      </div>
      {model.languages.length > 0 ? (
        <p className="text-xs text-pretty text-muted-foreground">
          {intl.formatMessage(
            {
              id: "speech_setup_card_languages_body",
              defaultMessage: "Works well in: {languages}",
            },
            { languages: listLanguages(model.languages) }
          )}
        </p>
      ) : null}
      {download ? (
        <InstallProgress
          event={download.event}
          onCancel={() => onCancel(download.id)}
        />
      ) : (
        <Button
          type="button"
          size="sm"
          className="self-start"
          // Only a build that cannot be installed here refuses.
          disabled={busy || (!model.installed_as && !model.build.can_install)}
          onClick={onSetUp}
        >
          {busy ? (
            <Spinner data-icon="inline-start" />
          ) : model.installed_as ? null : (
            <DownloadIcon data-icon="inline-start" />
          )}
          {model.installed_as
            ? intl.formatMessage({
                id: "speech_setup_card_use_button",
                defaultMessage: "Set up",
              })
            : intl.formatMessage({
                id: "speech_setup_card_download_button",
                defaultMessage: "Download and set up",
              })}
        </Button>
      )}
    </div>
  )
}
