import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getConnectionModels } from "./api"

/** Fetched only once asked for: listing a hosted catalog is a network call. */
export function useConnectionModels(connectionId: number, enabled: boolean) {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "remote", "connection", connectionId],
    queryFn: ({ signal }) => getConnectionModels(connectionId, signal),
    enabled,
  })
}
