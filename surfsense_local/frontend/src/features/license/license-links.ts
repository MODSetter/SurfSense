// Each must pass electron/src/main/external-url.ts, or the click does nothing.
// The portal has no accounts: the trial form sits on the downloads page beside
// the installers, and the pricing page is the only place a license is sold.
const SITE_URL = "https://www.surfsense.com"

export const TRIAL_URL = `${SITE_URL}/downloads`
export const PRICING_URL = `${SITE_URL}/pricing`
