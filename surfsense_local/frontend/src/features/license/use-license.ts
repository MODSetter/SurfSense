import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  downloadJobPacks,
  forgetDeliveries,
} from "@/features/jobs/packs/download-job-packs"
import { jobsKeys } from "@/features/jobs/query-keys"
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
 * unlocks, before anyone opens Plugins. Only a user's action publishes, so an
 * active license's jobs download from here, asking about the server first.
 */
export function usePublishLicense() {
  const queryClient = useQueryClient()
  return (status: LicenseStatus) => {
    queryClient.setQueryData(licenseQueryKey, status)
    void refreshLicenseVerdict(queryClient, { ifStale: false })
    // Which installed jobs may run follows the license.
    void queryClient.invalidateQueries({ queryKey: jobsKeys.packs() })
    // What the jobs' last downloads came to was said of the file this replaces.
    forgetDeliveries(queryClient)
    if (status.state === "active" && status.jobs.length > 0)
      void downloadJobPacks(queryClient, status.jobs)
  }
}
