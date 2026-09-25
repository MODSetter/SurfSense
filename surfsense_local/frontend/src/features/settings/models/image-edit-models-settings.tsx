import { InstallProgress } from "@/features/models/local/chat/install-progress"
import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useImageInstall } from "@/features/models/local/image/use-image-install"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"

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
  const { installState, cancelInstall } = useImageInstall()

  return (
    <ModelSlotSettings
      title="Image editing models"
      description="The model that edits images. Run one on this computer, or use one from a server."
      slot="image editing"
      modelType="image_edit"
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
