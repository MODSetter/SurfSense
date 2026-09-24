import { useMutation } from "@tanstack/react-query"

import { useRefreshModels } from "../../models-query"
import { deleteLocalAudioModel } from "./api"

export function useDeleteLocalAudioModel() {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (installedAs: string) => deleteLocalAudioModel(installedAs),
    onSuccess: () => refresh(),
  })
}
