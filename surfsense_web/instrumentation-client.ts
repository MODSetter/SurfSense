import posthog from "posthog-js";

if (process.env.NEXT_PUBLIC_POSTHOG_KEY) {
	posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
		api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
		defaults: "2025-11-30",
		// Disable automatic pageview capture, as we capture manually with PostHogProvider
		// This ensures proper pageview tracking with Next.js client-side navigation
		capture_pageview: "history_change",
		// Enable session recording
		capture_pageleave: true,
	});
}
