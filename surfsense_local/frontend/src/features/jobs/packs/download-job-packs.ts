import {
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query"
import { toast } from "sonner"

import { intl } from "@/i18n/intl"

import { requestPackDownload, type PackOutcome } from "../api"
import { jobTitle } from "../catalog"
import { jobsKeys } from "../query-keys"

export type Delivery =
  | { phase: "downloading" }
  | { phase: "done"; outcome: PackOutcome }
  | { phase: "failed"; error: unknown }

/** Each job's last download, by entitlement code. */
export type Deliveries = Readonly<Record<string, Delivery>>

const NO_DELIVERIES: Deliveries = {}

function record(queryClient: QueryClient, changes: Deliveries) {
  queryClient.setQueryData<Deliveries>(jobsKeys.delivery(), (current) => ({
    ...current,
    ...changes,
  }))
}

function each<T>(codes: readonly string[], value: T): Record<string, T> {
  return Object.fromEntries(codes.map((code) => [code, value]))
}

/**
 * Asks the app for every job the license includes. Only the user's own action
 * calls it (Download, or adding or renewing a license), so a license server
 * not yet allowed is asked about here, and tried once more on Allow.
 * Never throws: each code's outcome, or the failure, is left for the rows and
 * Settings › License to read, which say it rather than a toast.
 */
export async function downloadJobPacks(
  queryClient: QueryClient,
  entitlements: readonly string[]
): Promise<void> {
  const codes = [...new Set(entitlements)]
  const current =
    queryClient.getQueryData<Deliveries>(jobsKeys.delivery()) ?? NO_DELIVERIES
  if (codes.every((code) => current[code]?.phase === "downloading")) return
  record(queryClient, each(codes, { phase: "downloading" }))
  try {
    const answer = await requestPackDownload()
    // An older read still on its way must not land over the answer's listing.
    await queryClient.cancelQueries({ queryKey: jobsKeys.packs() })
    queryClient.setQueryData(jobsKeys.packs(), answer.packs)
    void queryClient.invalidateQueries({ queryKey: jobsKeys.settingsAll() })
    queryClient.setQueryData<Deliveries>(jobsKeys.delivery(), (before) => {
      const after: Record<string, Delivery> = { ...before }
      for (const code of codes) delete after[code]
      for (const outcome of answer.outcomes)
        after[outcome.entitlement] = { phase: "done", outcome }
      return after
    })
    for (const outcome of answer.outcomes) {
      if (outcome.outcome !== "installed") continue
      toast.success(
        intl.formatMessage(
          {
            id: "jobs_download_installed_toast",
            defaultMessage: "{job} is ready to run",
          },
          { job: jobTitle(outcome.entitlement) }
        )
      )
    }
  } catch (error) {
    record(queryClient, each(codes, { phase: "failed", error }))
  }
}

/**
 * Forgets what earlier downloads came to, once what they were about has
 * changed: a pack file imported for those jobs, or another license file.
 * Without `entitlements`, every job's. A download still out keeps its line,
 * and its answer is said when it comes.
 */
export function forgetDeliveries(
  queryClient: QueryClient,
  entitlements?: readonly string[]
): void {
  queryClient.setQueryData<Deliveries>(jobsKeys.delivery(), (current) => {
    if (!current) return current
    const kept = Object.entries(current).filter(
      ([code, delivery]) =>
        delivery.phase === "downloading" ||
        (entitlements !== undefined && !entitlements.includes(code))
    )
    return kept.length === Object.keys(current).length
      ? current
      : Object.fromEntries(kept)
  })
}

/** Client state, written by `downloadJobPacks` and cleared by
 *  `forgetDeliveries`: nothing fetches it. */
export function useDeliveries(): Deliveries {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: jobsKeys.delivery(),
    queryFn: () =>
      queryClient.getQueryData<Deliveries>(jobsKeys.delivery()) ??
      NO_DELIVERIES,
    initialData: NO_DELIVERIES,
    staleTime: Infinity,
  }).data
}
