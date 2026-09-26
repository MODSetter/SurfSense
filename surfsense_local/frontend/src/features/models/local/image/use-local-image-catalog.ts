import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalImageRows, type SdCppSlot } from "./api"

export function useLocalImageCatalog(slot: SdCppSlot = "image_gen") {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "image", slot],
    queryFn: ({ signal }) => getLocalImageRows(slot, signal),
  })
}
