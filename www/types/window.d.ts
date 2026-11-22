import type { PostHog } from "posthog-js";

declare global {
	interface Window {
		posthog?: PostHog;
	}
}
