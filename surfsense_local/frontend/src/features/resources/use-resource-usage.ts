import { useQuery } from "@tanstack/react-query"

import { getResourceUsage } from "./api"

// Fast enough to watch a model load, slow enough that the sample itself (about
// 40 ms in the API on Windows) stays out of what it measures.
const POLL_MS = 2000

/** Polls while mounted; TanStack pauses it while the window is hidden. */
export function useResourceUsage() {
  return useQuery({
    queryKey: ["resource-usage"],
    queryFn: ({ signal }) => getResourceUsage(signal),
    refetchInterval: POLL_MS,
    staleTime: 0,
  })
}
