import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../models-query"

import { getAvailableGenerationModels } from "./api"

// Under the shared models key, so a change made in settings reaches every list of them.
export const chatCandidatesQueryKey = [
  ...MODELS_QUERY_KEY,
  "chat-candidates",
] as const

/** Every model that can answer a chat right now; one read for every picker and screen. */
export function useChatCandidates() {
  return useQuery({
    queryKey: chatCandidatesQueryKey,
    queryFn: ({ signal }) => getAvailableGenerationModels(signal),
  })
}
