import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import type { ModelType } from "../../model-type"
import { MODELS_QUERY_KEY } from "../../models-query"
import { connectionIdQueryKey } from "../models/use-connection-models"
import { deleteConnection, getConnections, type Connection } from "./api"

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

/**
 * The connections that can fill `modelType`, by the backend's `serves`; none
 * for a step with no slot. The same query, so every list stays in step.
 */
export function useConnectionsServing(modelType: ModelType | null) {
  return useQuery({
    queryKey: connectionsQueryKey,
    queryFn: ({ signal }) => getConnections(signal),
    select: (connections) =>
      modelType
        ? connections.filter((connection) =>
            connection.serves.includes(modelType)
          )
        : [],
  })
}

/**
 * Removing a server clears every slot it filled, whichever section asked. The
 * server itself is taken off the list rather than asked about again: it would
 * answer "not found" on a card that is going.
 */
export function useDeleteConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteConnection(id),
    onSuccess: async (_deleted, id) => {
      const its = connectionIdQueryKey(id)
      queryClient.setQueryData<Connection[]>(
        connectionsQueryKey,
        (connections) =>
          connections?.filter((connection) => connection.id !== id)
      )
      await queryClient.invalidateQueries({
        queryKey: MODELS_QUERY_KEY,
        predicate: (query) =>
          !its.every((part, index) => query.queryKey[index] === part),
      })
    },
  })
}
