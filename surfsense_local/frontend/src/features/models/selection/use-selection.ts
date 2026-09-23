import { useMutation, useQuery } from "@tanstack/react-query"

import type { ModelType } from "../model-type"
import { MODELS_QUERY_KEY, useRefreshModels } from "../models-query"
import { getSelection, setSelection, type SelectionTarget } from "./api"

export const selectionQueryKey = (modelType: ModelType) =>
  [...MODELS_QUERY_KEY, "selection", modelType] as const

/** The model filling one slot, or null when nothing does. */
export function useSelection(modelType: ModelType) {
  return useQuery({
    queryKey: selectionQueryKey(modelType),
    queryFn: ({ signal }) => getSelection(modelType, signal),
  })
}

export function useSelect(modelType: ModelType) {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: ({
      target,
      allowUnlisted = false,
    }: {
      target: SelectionTarget
      allowUnlisted?: boolean
    }) => setSelection(modelType, target, undefined, allowUnlisted),
    onSuccess: () => refresh(),
  })
}
