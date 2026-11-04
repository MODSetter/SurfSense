import { useQueryClient } from "@tanstack/react-query"
import { useCallback } from "react"
import { toast } from "sonner"

import type { ChatMode, ChatModes } from "@/features/models/capability/api"
import { modelKey, type ModelSelection } from "@/features/models/selection/api"
import { selectionQueryKey } from "@/features/models/selection/use-selection"
import { intl } from "@/i18n/intl"
import { requestJson } from "@/lib/api"

import { usePickNewChatMode } from "./new-chat-mode"

function saveModePick(mode: ChatMode): Promise<ChatModes> {
  return requestJson<ChatModes>("/llm/selection/text_gen/mode", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  })
}

/**
 * A pick shows at once and is saved as the model's default, so a refresh or a
 * restart keeps it. Unsaved, it still holds for the session.
 */
export function useSaveModePick() {
  const pick = usePickNewChatMode()
  const client = useQueryClient()
  return useCallback(
    (model: ModelSelection, mode: ChatMode) => {
      pick(model, mode)
      saveModePick(mode).then(
        (modes) =>
          client.setQueryData<ModelSelection | null>(
            selectionQueryKey("text_gen"),
            (current) =>
              current?.capability && modelKey(current) === modelKey(model)
                ? { ...current, capability: { ...current.capability, modes } }
                : current
          ),
        () =>
          toast.error(
            intl.formatMessage({
              id: "chat_mode_picker_not_saved_toast",
              defaultMessage:
                "Couldn’t save this mode. New chats use it until you restart.",
            })
          )
      )
    },
    [pick, client]
  )
}
