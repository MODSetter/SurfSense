import type { Instrumentation } from "next";

const POSTHOG_COOKIE_RE = /ph_phc_.*?_posthog=([^;]+)/;

export function register() {
	// No-op — PostHog server client is lazily initialized
}

export const onRequestError: Instrumentation.onRequestError = async (err, request) => {
	if (process.env.NEXT_RUNTIME === "nodejs") {
		const { default: PostHogClient } = await import("./lib/posthog/server");

		try {
			const posthog = PostHogClient();

			let distinctId: string | undefined;
			const rawCookie = request.headers.cookie;
			if (rawCookie) {
				const cookieString = Array.isArray(rawCookie) ? rawCookie.join("; ") : rawCookie;
				const postHogCookieMatch = cookieString.match(POSTHOG_COOKIE_RE);
				if (postHogCookieMatch?.[1]) {
					try {
						const decodedCookie = decodeURIComponent(postHogCookieMatch[1]);
						const postHogData = JSON.parse(decodedCookie);
						distinctId = postHogData.distinct_id;
					} catch {
						// Cookie parsing failed — capture without distinct_id
					}
				}
			}

			await posthog.captureException(err, distinctId);
		} catch {
			// PostHog server capture failed — don't let it affect the request
		}
	}
};
