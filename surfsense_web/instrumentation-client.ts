import posthog from "posthog-js";

/**
 * PostHog initialisation for the Next.js renderer.
 *
 * The same bundle ships in two contexts:
 *   1. A normal browser session on surfsense.com  -> platform = "web"
 *   2. The Electron desktop app (renders the Next app from localhost)
 *      -> platform = "desktop"
 *
 * When running inside Electron we also seed `posthog-js` with the main
 * process's machine distinctId so that events fired from both the renderer
 * (e.g. `chat_message_sent`, page views) and the Electron main process
 * (e.g. `desktop_quick_ask_opened`) share a single PostHog person before
 * login, and can be merged into the authenticated user afterwards.
 */

function isElectron(): boolean {
	return typeof window !== "undefined" && !!window.electronAPI;
}

function currentPlatform(): "desktop" | "web" {
	return isElectron() ? "desktop" : "web";
}

async function resolveBootstrapDistinctId(): Promise<string | undefined> {
	if (!isElectron() || !window.electronAPI?.getAnalyticsContext) return undefined;
	try {
		const ctx = await window.electronAPI.getAnalyticsContext();
		return ctx?.machineId || ctx?.distinctId || undefined;
	} catch {
		return undefined;
	}
}

async function initPostHog() {
	try {
		if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;

		const platform = currentPlatform();
		const bootstrapDistinctId = await resolveBootstrapDistinctId();

		posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
			api_host: "https://assets.surfsense.com",
			ui_host: "https://us.posthog.com",
			defaults: "2026-01-30",
			capture_pageview: "history_change",
			capture_pageleave: true,
			...(bootstrapDistinctId
				? {
						bootstrap: {
							distinctID: bootstrapDistinctId,
							isIdentifiedID: false,
						},
					}
				: {}),
			before_send: (event) => {
				if (event?.properties) {
					event.properties.platform = platform;
					if (platform === "desktop") {
						event.properties.is_desktop = true;
					}

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
		requestIdleCallback(() => {
			void initPostHog();
		});
	} else {
		setTimeout(() => {
			void initPostHog();
		}, 3500);
	}
}
