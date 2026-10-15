import { usePendingInstalls } from "@/features/models/local/installs/pending-installs"
import { DownloadSpeechModels } from "@/features/models/local/transcription/download-speech-models"
import { SpeechLanguageSelect } from "@/features/models/local/transcription/language/speech-language-select"
import { useDeleteLocalSpeechModel } from "@/features/models/local/transcription/use-delete-local-speech-model"
import { useSelect } from "@/features/models/selection/use-selection"
import { useSpeechModels } from "@/features/models/your-models/use-speech-models"
import { intl } from "@/i18n/intl"

import { ModelSlotSettings } from "./model-slot-settings"

/** Speech recognition runs on this computer only: no server can fill it. */
export function SpeechModelsSettings() {
  const models = useSpeechModels()
  const select = useSelect("speech_to_text")
  const remove = useDeleteLocalSpeechModel()
  // Only downloads whose model can fill this slot, wherever they started.
  const pending = usePendingInstalls("speech_to_text")

  return (
    <ModelSlotSettings
      title={intl.formatMessage({
        id: "settings_speech_models_title",
        defaultMessage: "Speech recognition models",
      })}
      description={intl.formatMessage({
        id: "settings_speech_models_body",
        defaultMessage:
          "The model that turns recordings and voice input into text, on this computer.",
      })}
      slot="speech"
      modelType="speech_to_text"
      localOnly
      models={models}
      pending={pending}
      download={<DownloadSpeechModels />}
      inUseDetail={models.inUse ? <SpeechLanguageSelect /> : null}
      onUse={async (row) => {
        if (row.target) await select.mutateAsync({ target: row.target })
      }}
      onDelete={async (row) => {
        if (row.removeId) await remove.mutateAsync(row.removeId)
      }}
    />
  )
}
