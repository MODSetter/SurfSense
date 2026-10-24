import type { PostHog } from "posthog-js";

/** The part of the retired 0.0.x desktop app's bridge this site still calls. */
interface ElectronAPI {
	refreshAccessToken: () => Promise<string | null>;
	logout: () => Promise<void>;
	analyticsIdentify: (userId: string, properties?: Record<string, unknown>) => Promise<void>;
	analyticsReset: () => Promise<void>;
}

declare global {
	interface Window {
		posthog?: PostHog;
		electronAPI?: ElectronAPI;
	}
}
