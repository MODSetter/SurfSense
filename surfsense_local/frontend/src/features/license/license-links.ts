import { siteVisitUrl } from "@/features/external-links/site-visit-url"

// Each must pass electron/src/main/external-url.ts, or the click does nothing.
// The portal has no accounts: the pricing page is the only place a license is
// sold, and the trial opens it too, so the free plan is seen beside the paid.
const SITE_URL = "https://www.surfsense.com"

// Each link says which place in the app it was opened from, and the version.
export function trialUrl(version: string | undefined): string {
  return siteVisitUrl(`${SITE_URL}/pricing`, "license_trial", version)
}

export function pricingUrl(
  surface: "license_pricing" | "license_renew",
  version: string | undefined
): string {
  return siteVisitUrl(`${SITE_URL}/pricing`, surface, version)
}
