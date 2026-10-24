import posthog from "posthog-js";

/** Attributes a visit that arrived with `?ref=<code>`. Never throws: an ad-blocker can break posthog-js. */
export function trackReferralLanding(refCode: string, landingUrl: string) {
	try {
		posthog.capture("marketing_referral_landing", {
			ref_code: refCode,
			landing_url: landingUrl,
			$set_once: { first_ref_code: refCode },
			$set: { latest_ref_code: refCode },
		});
	} catch {
		// Analytics must never break the page.
	}
}
