import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"
import { usePendingInstalls } from "@/features/models/local/installs/pending-installs"
import { intl } from "@/i18n/intl"

import { ModelSlotSettings } from "./model-slot-settings"

/** The image section's parts for the editing slot. An image model that edits
 *  too, FLUX.2 klein, is listed in both, from the same files. */
export function ImageEditModelsSettings({
  onModelUnavailable,
}: {
  onModelUnavailable: () => void
}) {
  const models = useImageModels("image_edit")
  const select = useSelect("image_edit")
  const remove = useDeleteLocalImageModel()
  // One sd.cpp download at a time, shown in both sections.
  // Only downloads whose model can fill this slot, wherever they started.
  const pending = usePendingInstalls("image_edit")

  return (
    <ModelSlotSettings
      title={intl.formatMessage({
        id: "settings_image_edit_models_title",
        defaultMessage: "Image editing models",
      })}
      description={intl.formatMessage({
        id: "settings_image_edit_models_body",
        defaultMessage:
          "The model that edits images. Run one on this computer, or use one from a server.",
      })}
      slot="image_edit"
      modelType="image_edit"
      models={models}
      pending={pending}
      download={<DownloadImageModels slot="image_edit" />}
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
