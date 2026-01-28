import posthog from "posthog-js";

if (process.env.NEXT_PUBLIC_POSTHOG_KEY) {
	posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
		// Use reverse proxy to bypass ad blockers
		api_host: "/ingest",
		// Required for toolbar and other UI features to work correctly
		ui_host: "https://us.posthog.com",
		defaults: "2025-11-30",
		// Disable automatic pageview capture, as we capture manually with PostHogProvider
		// This ensures proper pageview tracking with Next.js client-side navigation
		capture_pageview: "history_change",
		// Enable session recording
		capture_pageleave: true,
		loaded: (posthog) => {
			// Expose PostHog to window for console access and toolbar
			if (typeof window !== "undefined") {
				window.posthog = posthog;
			}
		},
	});
}

// Always expose posthog to window for debugging/toolbar access
// This allows testing feature flags even without POSTHOG_KEY configured
if (typeof window !== "undefined") {
	window.posthog = posthog;
}
