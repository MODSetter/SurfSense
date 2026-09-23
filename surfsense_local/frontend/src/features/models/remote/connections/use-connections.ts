import { useMutation, useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY, useRefreshModels } from "../../models-query"
import { deleteConnection, getConnections } from "./api"

export const connectionsQueryKey = [
  ...MODELS_QUERY_KEY,
  "remote",
  "connections",
] as const

export function useConnections() {
  return useQuery({
    queryKey: connectionsQueryKey,
    queryFn: ({ signal }) => getConnections(signal),
  })
}

/** Removing a server clears every slot it filled, whichever section asked. */
export function useDeleteConnection() {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (id: number) => deleteConnection(id),
    onSuccess: () => refresh(),
  })
}
