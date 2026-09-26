import { InstallProgress } from "@/features/models/local/chat/install-progress"
import { DownloadAudioModels } from "@/features/models/local/audio/download-audio-models"
import { useAudioInstall } from "@/features/models/local/audio/use-audio-install"
import { useDeleteLocalAudioModel } from "@/features/models/local/audio/use-delete-local-audio-model"
import { useSelect } from "@/features/models/selection/use-selection"
import { useAudioModels } from "@/features/models/your-models/use-audio-models"
import { intl } from "@/i18n/intl"

import { ModelSlotSettings } from "./model-slot-settings"

export function AudioModelsSettings({
  onModelUnavailable,
}: {
  // A server removed from here can also be the one serving chat.
  onModelUnavailable: () => void
}) {
  const models = useAudioModels()
  const select = useSelect("audio_gen")
  const remove = useDeleteLocalAudioModel()
  const { installState, cancelInstall } = useAudioInstall()

  return (
    <ModelSlotSettings
      title={intl.formatMessage({
        id: "settings_audio_models_title",
        defaultMessage: "Audio generation models",
      })}
      description={intl.formatMessage({
        id: "settings_audio_models_body",
        defaultMessage: "The model that voices podcasts in Studio.",
      })}
      slot="audio"
      modelType="audio_gen"
      models={models}
      pending={
        installState.status === "installing" ? (
          <div className="flex flex-col gap-2">
            <p className="truncate text-sm font-medium">{installState.label}</p>
            <InstallProgress
              event={installState.event}
              onCancel={cancelInstall}
            />
          </div>
        ) : null
      }
      download={<DownloadAudioModels />}
      onChatCleared={onModelUnavailable}
      onUse={async (row) => {
        if (row.target) await select.mutateAsync({ target: row.target })
      }}
      onDelete={async (row) => {
        if (row.removeId) await remove.mutateAsync(row.removeId)
      }}
    />
  )
}
