import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalImageCatalog } from "./api"

// sd-server only starts once a model is chosen and its weights are on disk, so
// a fresh pick is selected-but-not-ready for a few seconds.
const STARTING_POLL_MS = 3000

export function useLocalImageCatalog() {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "image"],
    queryFn: ({ signal }) => getLocalImageCatalog(signal),
    refetchInterval: (query) => {
      const data = query.state.data
      const starting =
        data !== undefined &&
        !data.ready &&
        (data.models ?? []).some((model) => model.selected)
      return starting ? STARTING_POLL_MS : false
    },
  })
}
