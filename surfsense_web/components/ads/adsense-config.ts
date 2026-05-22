/**
 * Centralized AdSense ad slot IDs.
 *
 * After creating ad units in your AdSense dashboard (Ads → By ad unit), paste
 * the numeric slot IDs into the corresponding env vars below. Empty slot IDs
 * render nothing (see <AdUnit />), so partial rollout is safe.
 */
export const ADSENSE_SLOTS = {
	/** /free hub: between the model table and "Why SurfSense" section. */
	freeHubInContent: process.env.NEXT_PUBLIC_GOOGLE_ADSENSE_SLOT_FREE_HUB_IN_CONTENT ?? "",
	/** /free hub: between the CTA and the FAQ section. */
	freeHubBeforeFaq: process.env.NEXT_PUBLIC_GOOGLE_ADSENSE_SLOT_FREE_HUB_BEFORE_FAQ ?? "",
} as const;
