import { useQuery } from "@tanstack/react-query"

import { listJobPacks } from "./api"
import { jobsKeys } from "./query-keys"

/** The packs on this computer and what each may run. Never polled: the
 *  backend checks every pack's files again on each read. */
export function useJobPacks() {
  return useQuery({
    queryKey: jobsKeys.packs(),
    queryFn: ({ signal }) => listJobPacks(signal),
  })
}
