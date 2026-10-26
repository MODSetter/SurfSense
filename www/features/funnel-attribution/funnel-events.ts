import posthog from "posthog-js";
import type { TrialOutcome } from "./trial-outcome";

/**
 * The two funnel steps only the browser sees. They carry the channel tag and
 * never the email address typed into the form. The server-side steps
 * (`license_trial_issued`, `license_purchased`, `installer_download`) are
 * emitted personless by the backend and the download redirect.
 */

/** Skips the batch queue and goes by beacon, so it survives leaving for Stripe. */
const SURVIVES_NAVIGATION = { send_instantly: true, transport: "sendBeacon" } as const;

export function trackCheckoutStarted(channel: string): void {
	capture("checkout_started", { plan: "individual", channel }, SURVIVES_NAVIGATION);
}

export function trackTrialRequested(outcome: TrialOutcome, channel: string): void {
	capture("license_trial_requested", { outcome, channel });
}

function capture(
	event: string,
	properties: Record<string, string>,
	options?: typeof SURVIVES_NAVIGATION
): void {
	try {
		if (!posthog.__loaded) return;
		posthog.capture(event, properties, options);
	} catch {
		// Blocked or broken analytics must never break a form or a purchase.
	}
}
