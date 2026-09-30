import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { addServerVoice, readServerVoices, removeServerVoice } from "./api"

export const serverVoicesQueryKey = [
  ...MODELS_QUERY_KEY,
  "remote",
  "voices",
] as const

/** Keyed under the models, so choosing another model asks again. */
export function useServerVoices() {
  const client = useQueryClient()
  const refresh = () =>
    client.invalidateQueries({ queryKey: serverVoicesQueryKey })
  const voices = useQuery({
    queryKey: serverVoicesQueryKey,
    queryFn: ({ signal }) => readServerVoices(signal),
  })
  const add = useMutation({ mutationFn: addServerVoice, onSuccess: refresh })
  const remove = useMutation({
    mutationFn: removeServerVoice,
    onSuccess: refresh,
  })
  return { voices, add, remove }
}
