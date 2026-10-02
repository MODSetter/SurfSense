import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../models-query"
import { getLocalImageState, type SdCppSlot } from "./api"

/** Polled like Electron polls the runtime, so a started or stopped server shows. */
const POLL_MS = 5000

/** Asked only while a local model fills `slot`: otherwise there is nothing to say. */
export function useLocalImageState(slot: SdCppSlot, enabled: boolean) {
  return useQuery({
    queryKey: [...MODELS_QUERY_KEY, "local", "image", slot, "state"],
    queryFn: ({ signal }) => getLocalImageState(slot, signal),
    refetchInterval: POLL_MS,
    enabled,
  })
}
