import { DownloadChatModels } from "@/features/models/local/chat/download-chat-models"
import { InstallProgress } from "@/features/models/local/chat/install-progress"
import { useChatInstall } from "@/features/models/local/chat/use-chat-install"
import { useDeleteLocalChatModel } from "@/features/models/local/chat/use-delete-local-chat-model"
import type { ModelSelection } from "@/features/models/selection/api"
import { useSelect } from "@/features/models/selection/use-selection"
import { useChatModels } from "@/features/models/your-models/use-chat-models"

import { ModelSlotSettings } from "./model-slot-settings"

export function ChatModelsSettings({
  onSelected,
  onModelUnavailable,
}: {
  onSelected: (selection: ModelSelection) => void
  onModelUnavailable: () => void
}) {
  const models = useChatModels()
  const select = useSelect("text_gen")
  const remove = useDeleteLocalChatModel(onModelUnavailable)
  const { installState, cancelInstall } = useChatInstall()

  return (
    <ModelSlotSettings
      title="Text generation models"
      description="The model that answers in chat. Run one on this computer, or use one from a server."
      slot="chat"
      modelType="text_gen"
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
      download={
        <DownloadChatModels
          onSelected={onSelected}
          onModelUnavailable={onModelUnavailable}
        />
      }
      onSelected={onSelected}
      onChatCleared={onModelUnavailable}
      onUse={async (row) => {
        if (!row.target) return
        onSelected(await select.mutateAsync({ target: row.target }))
      }}
      onDelete={async (row) => {
        if (row.removeId) await remove.mutateAsync(row.removeId)
      }}
    />
  )
}
