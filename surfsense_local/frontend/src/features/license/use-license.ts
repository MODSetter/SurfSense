import { useQuery, useQueryClient } from "@tanstack/react-query"

import { refreshLicenseVerdict } from "@/features/plugins/license-verdict"

import { readLicense, type LicenseStatus } from "./api"

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

/**
 * Straight into the cache rather than a refetch, so the sidebar's license row
 * reacts without fetching; the paid plugins then show what the new license
 * unlocks, before anyone opens Plugins.
 */
export function usePublishLicense() {
  const queryClient = useQueryClient()
  return (status: LicenseStatus) => {
    queryClient.setQueryData(licenseQueryKey, status)
    void refreshLicenseVerdict(queryClient, { ifStale: false })
  }
}
