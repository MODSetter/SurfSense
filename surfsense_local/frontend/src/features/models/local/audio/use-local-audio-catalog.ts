import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalAudioCatalog } from "./api"

export function useLocalAudioCatalog() {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "audio"],
    queryFn: ({ signal }) => getLocalAudioCatalog(signal),
  })
}
