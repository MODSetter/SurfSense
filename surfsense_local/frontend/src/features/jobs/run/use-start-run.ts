import { useMutation, useQueryClient } from "@tanstack/react-query"

import { studioKeys } from "@/features/studio/query-keys"

import { startJobRun, type JobRunStart } from "../api"
import { jobsKeys } from "../query-keys"

/** Starts a run. The route answers only the run's id, so Studio's list and the
 *  recent runs are read again to show its copy. */
export function useStartRun(
  workspaceId: number,
  onStarted: (runId: number) => void
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (run: JobRunStart) => startJobRun(workspaceId, run),
    onSuccess: ({ artifact_id }) => {
      void queryClient.invalidateQueries({
        queryKey: studioKeys.artifacts(workspaceId),
      })
      void queryClient.invalidateQueries({
        queryKey: jobsKeys.runs(workspaceId),
      })
      onStarted(artifact_id)
    },
  })
}
