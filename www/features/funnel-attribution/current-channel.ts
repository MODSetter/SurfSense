import posthog from "posthog-js";
import { REF_STORAGE_KEY } from "@/features/analytics/PostHogReferral";
import { channelFor, DIRECT_CHANNEL, type Touch, touchFromUrl } from "./channel-tag";

/**
 * The visitor's channel, from what the site already records and nothing new:
 * PostHog's first-touch page and referrer, the `?ref` code `PostHogReferral`
 * keeps for the session, then this page's own URL and referrer. Every source
 * may be missing (analytics blocked, storage refused), so each one is optional.
 */
export function currentChannel(): string {
	if (typeof window === "undefined") return DIRECT_CHANNEL;
	const touches: Touch[] = [];
	const firstTouch = postHogFirstTouch();
	if (firstTouch) touches.push(firstTouch);
	const sessionRef = sessionRefCode();
	if (sessionRef) touches.push({ ref: sessionRef });
	touches.push(touchFromUrl(window.location.href, document.referrer));
	return channelFor(touches, window.location.hostname);
}

/** `$initial_person_info` is posthog-js's first-touch record: `u` the landing URL, `r` its referrer. */
function postHogFirstTouch(): Touch | null {
	try {
		if (!posthog.__loaded) return null;
		const info = posthog.get_property("$initial_person_info") as unknown;
		if (!info || typeof info !== "object") return null;
		const { u, r } = info as { u?: unknown; r?: unknown };
		return touchFromUrl(typeof u === "string" ? u : null, typeof r === "string" ? r : null);
	} catch {
		return null;
	}
}

function sessionRefCode(): string | null {
	try {
		return window.sessionStorage.getItem(REF_STORAGE_KEY);
	} catch {
		return null;
	}
}
