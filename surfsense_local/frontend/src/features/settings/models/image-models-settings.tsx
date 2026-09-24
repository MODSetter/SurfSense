import { InstallProgress } from "@/features/models/local/chat/install-progress"
import { DownloadImageModels } from "@/features/models/local/image/download-image-models"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"
import { useImageInstall } from "@/features/models/local/image/use-image-install"
import { useSelect } from "@/features/models/selection/use-selection"
import { useImageModels } from "@/features/models/your-models/use-image-models"
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
  const { installState, cancelInstall } = useImageInstall()

  return (
    <ModelSlotSettings
      title={intl.formatMessage({ id: "settings_image_models_title" })}
      description={intl.formatMessage({ id: "settings_image_models_body" })}
      slot="image"
      modelType="image_gen"
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
