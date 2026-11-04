import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { readJobSettings, saveJobSettings, type JobSettingsWrite } from "../api"
import { jobsKeys } from "../query-keys"

/** The firm's choices for a job, read by its settings and by the run form's checker line. */
export function useJobSettings(job: string) {
  return useQuery({
    queryKey: jobsKeys.settings(job),
    queryFn: ({ signal }) => readJobSettings(job, signal),
  })
}

export function useSaveJobSettings(job: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (settings: JobSettingsWrite) => saveJobSettings(job, settings),
    onSuccess: (saved) =>
      queryClient.setQueryData(jobsKeys.settings(job), saved),
  })
}
