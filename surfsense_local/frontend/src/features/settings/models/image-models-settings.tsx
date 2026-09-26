import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"
import { usePendingInstalls } from "@/features/models/local/installs/pending-installs"
import { intl } from "@/i18n/intl"

import { ModelSlotSettings } from "./model-slot-settings"

export function ImageModelsSettings({
  onModelUnavailable,
}: {
  // A server removed from here can also be the one serving chat.
  onModelUnavailable: () => void
}) {
  const models = useImageModels()
  const select = useSelect("image_gen")
  const remove = useDeleteLocalImageModel()
  // Only downloads whose model can fill this slot, wherever they started.
  const pending = usePendingInstalls("image_gen")

  return (
    <ModelSlotSettings
      title={intl.formatMessage({
        id: "settings_image_models_title",
        defaultMessage: "Image generation models",
      })}
      description={intl.formatMessage({
        id: "settings_image_models_body",
        defaultMessage:
          "The model that makes images in Studio. Run one on this computer, or use one from a server.",
      })}
      slot="image"
      modelType="image_gen"
      models={models}
      pending={pending}
      download={<DownloadImageModels />}
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
