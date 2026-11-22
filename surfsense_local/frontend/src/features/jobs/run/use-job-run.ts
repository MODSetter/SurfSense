import { skipToken, useQuery } from "@tanstack/react-query"

import { readJobRun } from "../api"
import { jobsKeys } from "../query-keys"

import { isRunning } from "./run-stage"

// A run writes its progress, not an event, so an open run is re-read while it
// goes on; two seconds keeps "12 of 40 questions" moving.
export const RUN_POLL_MS = 2000

/**
 * One run, read by any version of its copy; null when that copy is no job's.
 * The Jobs screen polls it while it goes on; Studio leaves the refresh to its
 * own artifact events, which re-read every run of the workspace.
 */
export function useJobRun(
  workspaceId: number | null,
  rootId: number | null,
  { poll = false }: { poll?: boolean } = {}
) {
  const known = workspaceId !== null && rootId !== null
  return useQuery({
    queryKey: known
      ? jobsKeys.run(workspaceId, rootId)
      : [...jobsKeys.all, "no-run"],
    queryFn: known
      ? ({ signal }) => readJobRun(workspaceId, rootId, signal)
      : skipToken,
    refetchInterval: ({ state: { data } }) =>
      poll && data && (data.running || isRunning(data.status))
        ? RUN_POLL_MS
        : false,
  })
}
