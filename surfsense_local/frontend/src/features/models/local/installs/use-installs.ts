import { useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import type { InstallJob } from "./api"
import { retainInstallFeed } from "./feed"
import { INSTALLS_QUERY_KEY } from "./installs-query-key"

const NONE: InstallJob[] = []

/** Every install the API reports, kept current by its feed. */
export function useInstalls(): InstallJob[] {
  const client = useQueryClient()
  useEffect(() => retainInstallFeed(client), [client])
  const query = useQuery({
    queryKey: INSTALLS_QUERY_KEY,
    // Only the feed writes it, so nothing here can race a newer frame.
    queryFn: () =>
      client.getQueryData<InstallJob[]>(INSTALLS_QUERY_KEY) ?? NONE,
    enabled: false,
  })
  return query.data ?? NONE
}
