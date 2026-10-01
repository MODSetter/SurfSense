import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "@/features/models/models-query"

import { getEmbeddingIndex } from "./api"

export const embeddingIndexQueryKey = [
  ...MODELS_QUERY_KEY,
  "embedding",
] as const

export function useEmbeddingIndex() {
  return useQuery({
    queryKey: embeddingIndexQueryKey,
    queryFn: ({ signal }) => getEmbeddingIndex(signal),
  })
}
