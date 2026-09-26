import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"
import { usePendingInstalls } from "@/features/models/local/installs/pending-installs"
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
  // Only downloads whose model can fill this slot, wherever they started.
  const pending = usePendingInstalls("video_gen")

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
      pending={pending}
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
