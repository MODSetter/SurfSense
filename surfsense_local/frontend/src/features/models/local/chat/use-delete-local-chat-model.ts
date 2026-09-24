import { useMutation } from "@tanstack/react-query"

import { useRefreshModels } from "../../models-query"
import { deleteLocalModel } from "./api"

/** Deleting the model in use clears the chat slot; the server says when. */
export function useDeleteLocalChatModel(onChatCleared?: () => void) {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (installedAs: string) => deleteLocalModel(installedAs),
    onSuccess: async (result) => {
      if (result.selection_cleared) onChatCleared?.()
      await refresh()
    },
  })
}
