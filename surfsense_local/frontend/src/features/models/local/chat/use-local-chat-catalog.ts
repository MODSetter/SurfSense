import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getModelCatalog } from "./api"

export const localChatCatalogQueryKey = [
  ...MODELS_QUERY_KEY,
  "local",
  "chat",
] as const

// No refresh parameter and no rescan: the catalog is the manifest plus a
// directory listing, priced locally, so there is nothing to re-probe.
export function useLocalChatCatalog() {
  return useQuery({
    queryKey: localChatCatalogQueryKey,
    queryFn: ({ signal }) => getModelCatalog(signal),
  })
}
