import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalImageCatalog } from "./api"

export function useLocalImageCatalog() {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "image"],
    queryFn: ({ signal }) => getLocalImageCatalog(signal),
  })
}
