import posthog from "posthog-js";

/**
 * PostHog initialisation for the Next.js renderer.
 *
 * Every event and person is stamped `platform: "web"`. Dashboards filter on it,
 * so it stays although the retired 0.0.x desktop app, which was "desktop", no
 * longer opens the site.
 */

const platform = "web";

async function initPostHog() {
	try {
		if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;

		posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
			api_host: "https://assets.surfsense.com",
			ui_host: "https://us.posthog.com",
			defaults: "2026-01-30",
			capture_pageview: "history_change",
			capture_pageleave: true,
			before_send: (event) => {
				if (event?.properties) {
					event.properties.platform = platform;

					const params = new URLSearchParams(window.location.search);
					const ref = params.get("ref");
					if (ref) {
						event.properties.ref_code = ref;
						event.properties.$set = {
							...event.properties.$set,
							initial_ref_code: ref,
						};
						event.properties.$set_once = {
							...event.properties.$set_once,
							first_ref_code: ref,
						};
					}

					event.properties.$set = {
						...event.properties.$set,
						platform,
						last_seen_at: new Date().toISOString(),
					};

					event.properties.$set_once = {
						...event.properties.$set_once,
						first_seen_platform: platform,
					};
				}
				return event;
			},
			loaded: () => {
				if (typeof window !== "undefined") {
					// `loaded` hands back a `PostHogInterface`, but it's the same
					// singleton as the default import (typed `PostHog`); use that to
					// keep `window.posthog` correctly typed.
					window.posthog = posthog;
				}
			},
		});
	} catch {
		// PostHog init failed (likely ad-blocker) – app must continue to work
	}
}

if (typeof window !== "undefined") {
	window.posthog = posthog;

	if ("requestIdleCallback" in window) {
		requestIdleCallback(() => {
			void initPostHog();
		});
	} else {
		setTimeout(() => {
			void initPostHog();
		}, 3500);
	}
}
