import { useMutation } from "@tanstack/react-query"

import { useRefreshModels } from "../models-query"
import { setAgentTrial } from "./api"

/** Turns the agent trial on or off for the selected chat model. */
export function useAgentTrial() {
  const refresh = useRefreshModels()
  return useMutation({
    mutationFn: (enabled: boolean) => setAgentTrial(enabled),
    onSuccess: () => refresh(),
  })
}
