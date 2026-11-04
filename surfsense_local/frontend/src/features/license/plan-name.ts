import type { LicenseStatus } from "./api"

// Plan names are product names and stay English. A one-person Business license
// is sold, and shown, as Solo (ADR 0079).
export function planName({
  plan,
  max_users,
}: Pick<LicenseStatus, "plan" | "max_users">): string {
  if (plan === "business" && max_users === 1) return "Solo"
  const name = plan ?? ""
  return `${name.charAt(0).toUpperCase()}${name.slice(1)}`
}
