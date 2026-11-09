import { useMutation, useQueryClient } from "@tanstack/react-query"

import { allowAll } from "@/features/egress/api"
import { askEgress } from "@/features/egress/ask-egress"
import { ApiError } from "@/lib/api"

import { refreshLicense, type LicenseStatus } from "./api"
import { licenseQueryKey, usePublishLicense } from "./use-license"

/** `renewed` when the fetched file ends later than the one shown before. */
export type RenewalCheck = { status: LicenseStatus; renewed: boolean }

/** Settings' Check for renewal: fetches the stored license's renewed file and publishes what it leaves. */
export function useLicenseRefresh() {
  const queryClient = useQueryClient()
  const publish = usePublishLicense()
  return useMutation({
    mutationFn: async (): Promise<RenewalCheck> => {
      const shown = queryClient.getQueryData<LicenseStatus>(licenseQueryKey)
      const status = await refreshWithConsent()
      return {
        status,
        renewed: endsLater(status.expiry, shown?.expiry ?? null),
      }
    },
    onSuccess: ({ status }) => publish(status),
  })
}

export type LicenseRefresh = ReturnType<typeof useLicenseRefresh>

/**
 * A license server not yet allowed is asked about, as a refused user action
 * is, and the check is tried once more on Allow (ADR 0017). On Cancel the
 * refusal stands, and its message says where to allow the host.
 */
async function refreshWithConsent(): Promise<LicenseStatus> {
  try {
    return await refreshLicense()
  } catch (error) {
    if (!(error instanceof ApiError) || error.code !== "refresh_egress_blocked")
      throw error
    if (!(await askEgress(questionFor(error)))) throw error
    return refreshLicense()
  }
}

// The refusal carries the fields an `egress_disabled` one does.
function questionFor(refusal: ApiError) {
  const { destination, host, hosts, purpose } = refusal.detail
  const key = String(destination ?? "")
  const first = String(host ?? "")
  const also = Array.isArray(hosts)
    ? hosts.filter(
        (each): each is string => typeof each === "string" && each !== first
      )
    : []
  return {
    destination: key,
    host: first,
    purpose: typeof purpose === "string" ? purpose : undefined,
    also,
    allow: () => allowAll(key, also),
  }
}

// A renewal moves the expiry later on the same key (contract 1, producer rule 7).
function endsLater(next: string | null, shown: string | null) {
  return next !== null && shown !== null && Date.parse(next) > Date.parse(shown)
}
