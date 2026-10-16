import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalSpeechModels } from "./api"

export function useLocalSpeechCatalog() {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "speech"],
    queryFn: ({ signal }) => getLocalSpeechModels(signal),
  })
}
