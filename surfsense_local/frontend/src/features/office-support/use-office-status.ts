import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"

import { followOffice, getOfficeStatus, officeQueryKey } from "./api"

const RETRY_MS = 5_000

/** Office support's state, kept current from the API's event stream while shown. */
export function useOfficeStatus() {
  const client = useQueryClient()
  const status = useQuery({
    queryKey: officeQueryKey,
    queryFn: ({ signal }) => getOfficeStatus(signal),
  })

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    async function follow() {
      try {
        for await (const frame of followOffice(controller.signal)) {
          client.setQueryData(officeQueryKey, frame)
        }
      } catch {
        // A dropped stream is retried; the query keeps the last state meanwhile.
      }
      if (!controller.signal.aborted) timer = setTimeout(follow, RETRY_MS)
    }
    void follow()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [client])

  return status
}
