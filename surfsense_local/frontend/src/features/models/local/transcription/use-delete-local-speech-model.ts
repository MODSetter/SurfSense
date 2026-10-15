import { useMutation } from "@tanstack/react-query"

import { useRefreshModels } from "../../models-query"
import { deleteLocalSpeechModel } from "./api"

export function useDeleteLocalSpeechModel() {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (installedAs: string) => deleteLocalSpeechModel(installedAs),
    onSuccess: () => refresh(),
  })
}
