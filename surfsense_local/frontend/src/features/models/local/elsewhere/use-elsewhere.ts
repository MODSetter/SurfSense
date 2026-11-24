import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import {
  addFolder,
  type Elsewhere,
  getElsewhere,
  removeFolder,
  setLook,
} from "./api"

// Under the models key, so an install that ends refreshes it with the rest.
export const elsewhereQueryKey = [
  ...MODELS_QUERY_KEY,
  "local",
  "elsewhere",
] as const

/** The chat models other apps downloaded here. Asking again is a folder
 *  listing: the server keeps each header it has read. */
export function useElsewhere() {
  return useQuery({
    queryKey: elsewhereQueryKey,
    queryFn: ({ signal }) => getElsewhere(signal),
  })
}

/** The switch for looking and the added folders; each answer is the new list. */
export function useElsewhereSettings() {
  const client = useQueryClient()
  const settle = (next: Elsewhere) =>
    client.setQueryData(elsewhereQueryKey, next)
  return {
    look: useMutation({ mutationFn: setLook, onSuccess: settle }),
    addFolder: useMutation({ mutationFn: addFolder, onSuccess: settle }),
    removeFolder: useMutation({ mutationFn: removeFolder, onSuccess: settle }),
  }
}
