"use client";

import { useEffect } from "react";
import { trackReferralLanding } from "@/lib/posthog/events";

const REF_STORAGE_KEY = "surfsense_ref_code";

/**
 * Captures the ?ref=<code> URL parameter on first landing and fires a
 * PostHog event so marketing campaigns can be attributed.
 *
 * The ref code is persisted to sessionStorage so it survives client-side
 * navigations that strip query params (e.g. login redirect), but a fresh
 * event is fired for each new browser session with a ref param.
 */
export function PostHogReferral() {
	useEffect(() => {
		if (typeof window === "undefined") return;

		const params = new URLSearchParams(window.location.search);
		const ref = params.get("ref");

		if (ref) {
			try {
				sessionStorage.setItem(REF_STORAGE_KEY, ref);
			} catch {
				// Private browsing may block sessionStorage
			}
			trackReferralLanding(ref, window.location.href);
		}
	}, []);

	return null;
}
