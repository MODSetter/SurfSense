import { useQuery } from "@tanstack/react-query"

import { readLicense } from "./api"

export const licenseQueryKey = ["license"] as const

/**
 * Shared, so Settings and the sidebar cannot disagree about what is installed.
 * Importing a file writes the result straight into this cache; every reader
 * re-renders off the same value rather than each fetching its own.
 */
export function useLicense() {
  return useQuery({
    queryKey: licenseQueryKey,
    queryFn: ({ signal }) => readLicense(signal),
  })
}
