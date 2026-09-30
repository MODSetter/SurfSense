import { useQuery } from "@tanstack/react-query"

import { getResourceUsage } from "./api"

// Fast enough to watch a model load, slow enough that the sample itself (about
// 40 ms in the API on Windows) stays out of what it measures.
const POLL_MS = 2000

/** Polls only while shown; TanStack also pauses while the window is hidden. */
export function useResourceUsage(enabled: boolean) {
  return useQuery({
    queryKey: ["resource-usage"],
    queryFn: ({ signal }) => getResourceUsage(signal),
    enabled,
    refetchInterval: POLL_MS,
    staleTime: 0,
  })
}
