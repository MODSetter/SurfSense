import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import type { Connection } from "../connections/api"
import { getConnectionModels } from "./api"

type Identity = Pick<Connection, "id" | "created_at">

/** Every query about one connection id, whichever connection held it. */
export function connectionIdQueryKey(id: number) {
  return [...MODELS_QUERY_KEY, "remote", "connection", id] as const
}

/**
 * By the connection, not its id alone: SQLite gives a deleted connection's id
 * to the next one, which must never see the last one's models.
 */
export function connectionModelsQueryKey(connection: Identity) {
  return [
    ...connectionIdQueryKey(connection.id),
    connection.created_at,
  ] as const
}

/** Fetched only once asked for: listing a hosted catalog is a network call. */
export function useConnectionModels(connection: Identity, enabled: boolean) {
  return useQuery({
    queryKey: connectionModelsQueryKey(connection),
    queryFn: ({ signal }) => getConnectionModels(connection.id, signal),
    enabled,
  })
}
