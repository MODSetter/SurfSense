import { useQuery } from "@tanstack/react-query"

import { listJobRuns } from "../api"
import { jobsKeys } from "../query-keys"

// The list shows ten; an eleventh says older runs exist.
export const RUNS_SHOWN = 10
// Progress is written to a run, not announced, so a list with one going is re-read.
export const RUNS_POLL_MS = 5000

export function useJobRuns(workspaceId: number) {
  return useQuery({
    queryKey: jobsKeys.runs(workspaceId),
    queryFn: ({ signal }) => listJobRuns(workspaceId, RUNS_SHOWN + 1, signal),
    refetchInterval: ({ state: { data } }) =>
      data?.some((run) => run.running) ? RUNS_POLL_MS : false,
  })
}
