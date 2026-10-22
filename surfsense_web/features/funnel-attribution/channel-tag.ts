/**
 * The channel a visitor came from, as one short tag: a referral code, a
 * campaign's utm_source, the referring site's domain, or "direct".
 *
 * This is the only attribution sent with a trial request or a checkout. It
 * names a channel, never a person or a browser, so it can travel to Stripe and
 * the licence server without joining anyone's browsing to their email.
 */

export const DIRECT_CHANNEL = "direct";

/** The backend's cap; Stripe's `client_reference_id` allows more. */
const MAX_LENGTH = 40;

/** One visit's worth of evidence: the landing URL's tags and its referrer. */
export type Touch = {
	ref?: string | null;
	utmSource?: string | null;
	referrer?: string | null;
};

/** Lowercase `[a-z0-9_-]`, at most 40 characters, or null when nothing is left. */
export function toChannelTag(raw: string | null | undefined): string | null {
	if (!raw) return null;
	const tag = raw
		.toLowerCase()
		.replace(/[^a-z0-9_-]+/g, "-")
		.replace(/^-+/, "")
		.slice(0, MAX_LENGTH)
		.replace(/-+$/, "");
	return tag || null;
}

function isOwnHost(host: string, ownHost: string): boolean {
	const own = ownHost.replace(/^www\./, "");
	return host === own || host === "surfsense.com" || host.endsWith(".surfsense.com");
}

/** The referring site's domain without `www.`, or null for our own pages and non-URLs. */
export function referrerDomain(
	referrer: string | null | undefined,
	ownHost: string
): string | null {
	if (!referrer) return null;
	try {
		const host = new URL(referrer).hostname.replace(/^www\./, "");
		return host && !isOwnHost(host, ownHost) ? host : null;
	} catch {
		return null;
	}
}

/** The tags a landing URL carried, with the referrer it arrived from. */
export function touchFromUrl(url: string | null | undefined, referrer?: string | null): Touch {
	try {
		const params = url ? new URL(url).searchParams : null;
		return { ref: params?.get("ref"), utmSource: params?.get("utm_source"), referrer };
	} catch {
		return { referrer };
	}
}

/**
 * Touches run oldest first. An explicit tag beats a referrer, so a campaign
 * link still counts after the visitor wandered off through search; among
 * tags, and then among referrers, the earliest wins.
 */
export function channelFor(touches: Touch[], ownHost: string): string {
	for (const touch of touches) {
		const tag = toChannelTag(touch.ref) ?? toChannelTag(touch.utmSource);
		if (tag) return tag;
	}
	for (const touch of touches) {
		const tag = toChannelTag(referrerDomain(touch.referrer, ownHost));
		if (tag) return tag;
	}
	return DIRECT_CHANNEL;
}
