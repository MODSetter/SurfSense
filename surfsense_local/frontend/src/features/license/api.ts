import { requestJson, requestVoid } from "@/lib/api"

export type LicenseState =
  "none" | "active" | "license_expired" | "clock_untrusted"

export type LicenseStatus = {
  state: LicenseState
  plan: string | null
  email: string | null
  expiry: string | null
  // A team key's seats, a business key's people.
  max_users: number | null
  // A business license's firm, as typed at checkout.
  firm: string | null
  // Entitlement codes of the job plugins it unlocks, such as JOB_QUESTIONNAIRE.
  jobs: string[]
}

export function readLicense(signal?: AbortSignal): Promise<LicenseStatus> {
  return requestJson<LicenseStatus>("/license/status", { signal })
}

export function importLicense(certificate: string): Promise<LicenseStatus> {
  return requestJson<LicenseStatus>("/license", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ certificate }),
  })
}

export function removeLicense(): Promise<void> {
  return requestVoid("/license", { method: "DELETE" })
}

// No body: the backend sends the stored license's key to SurfSense's license
// server and imports the file it answers, as a re-import would.
export function refreshLicense(): Promise<LicenseStatus> {
  return requestJson<LicenseStatus>("/license/refresh", { method: "POST" })
}
