import { useMutation } from "@tanstack/react-query"

import { useRefreshModels } from "../../models-query"
import { deleteLocalImageModel } from "./api"

export function useDeleteLocalImageModel() {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (installedAs: string) => deleteLocalImageModel(installedAs),
    onSuccess: () => refresh(),
  })
}
