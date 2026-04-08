import posthog from "posthog-js";

function initPostHog() {
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
						last_seen_at: new Date().toISOString(),
					};
				}
				return event;
			},
			loaded: (ph) => {
				if (typeof window !== "undefined") {
					window.posthog = ph;
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
		requestIdleCallback(initPostHog);
	} else {
		setTimeout(initPostHog, 3500);
	}
}
