import { InstallProgress } from "@/features/models/local/chat/install-progress"
import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useImageInstall } from "@/features/models/local/image/use-image-install"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"
import { intl } from "@/i18n/intl"

import { ModelSlotSettings } from "./model-slot-settings"

/** The image section's parts for the video slot: sd-server runs video models
 *  too, and a model is listed here only when its entry makes it one. */
export function VideoModelsSettings({
  onModelUnavailable,
}: {
  onModelUnavailable: () => void
}) {
  const models = useImageModels("video_gen")
  const select = useSelect("video_gen")
  const remove = useDeleteLocalImageModel()
  // One sd.cpp download at a time, shown in every sd.cpp section.
  const { installState, cancelInstall } = useImageInstall()

  return (
    <ModelSlotSettings
      title={intl.formatMessage({
        id: "settings_video_models_title",
        defaultMessage: "Video generation models",
      })}
      description={intl.formatMessage({
        id: "settings_video_models_body",
        defaultMessage:
          "The model that makes video. Run one on this computer, or use one from a server.",
      })}
      slot="video"
      modelType="video_gen"
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
      download={<DownloadImageModels slot="video_gen" />}
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
