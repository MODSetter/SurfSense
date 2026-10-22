import { siteVisitUrl } from "@/features/external-links/site-visit-url"

// Each must pass electron/src/main/external-url.ts, or the click does nothing.
// The portal has no accounts: the trial form sits on the downloads page beside
// the installers, and the pricing page is the only place a license is sold.
const SITE_URL = "https://www.surfsense.com"

// Each link says which place in the app it was opened from, and the version.
export function trialUrl(version: string | undefined): string {
  return siteVisitUrl(`${SITE_URL}/downloads`, "license_trial", version)
}

export function pricingUrl(
  surface: "license_pricing" | "license_renew",
  version: string | undefined
): string {
  return siteVisitUrl(`${SITE_URL}/pricing`, surface, version)
}
