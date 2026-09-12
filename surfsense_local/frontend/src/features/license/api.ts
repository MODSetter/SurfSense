import { requestJson, requestVoid } from "@/lib/api"

export type LicenseState =
  "none" | "active" | "license_expired" | "clock_untrusted"

export type LicenseStatus = {
  state: LicenseState
  plan: string | null
  email: string | null
  expiry: string | null
  max_users: number | null
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
