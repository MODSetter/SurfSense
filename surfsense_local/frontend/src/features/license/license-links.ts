import { siteVisitUrl } from "@/features/external-links/site-visit-url"

// Each must pass electron/src/main/external-url.ts, or the click does nothing.
// The portal has no accounts: the pricing page is the only place a license is
// sold. Settings' trial opens it too, so the free plan is seen beside the paid;
// a job's trial opens the download page, where the Business trial's form is
// (ADR 0079).
const SITE_URL = "https://www.surfsense.com"

const TRIAL_PAGES = {
  license_trial: "/pricing",
  jobs_trial: "/downloads",
} as const

export type TrialSurface = keyof typeof TRIAL_PAGES

// Each link says which place in the app it was opened from, and the version.
export function trialUrl(
  version: string | undefined,
  surface: TrialSurface = "license_trial"
): string {
  return siteVisitUrl(`${SITE_URL}${TRIAL_PAGES[surface]}`, surface, version)
}

export function pricingUrl(
  surface: "license_pricing" | "license_renew" | "jobs_pricing",
  version: string | undefined
): string {
  return siteVisitUrl(`${SITE_URL}/pricing`, surface, version)
}

// A computer without internet gets its job pack file from support by hand.
export function supportUrl(
  surface: "jobs_support" | "license_jobs_support",
  version: string | undefined
): string {
  return siteVisitUrl(`${SITE_URL}/contact`, surface, version)
}
