import posthog from "posthog-js";

function initPostHog() {
	if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;

	posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
		api_host: "/ingest",
		ui_host: "https://us.posthog.com",
		defaults: "2025-11-30",
		capture_pageview: "history_change",
		capture_pageleave: true,
		before_send: (event) => {
			if (event.properties) {
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
}

if (typeof window !== "undefined") {
	window.posthog = posthog;

	if ("requestIdleCallback" in window) {
		requestIdleCallback(initPostHog);
	} else {
		setTimeout(initPostHog, 3500);
	}
}
