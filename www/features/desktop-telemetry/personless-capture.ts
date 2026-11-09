import { randomUUID } from "node:crypto";
import { PostHog, type PostHogOptions } from "posthog-node";

/** An event with no person behind it; every value is an enum, flag or fixed format. */
export type PersonlessEvent = {
	event: string;
	properties: Record<string, string | number | boolean>;
};

export type CapturePersonless = (event: PersonlessEvent) => Promise<void>;

type CaptureConfig = {
	apiKey: string | undefined;
	host: string | undefined;
	fetch?: PostHogOptions["fetch"];
};

/**
 * Sends one event straight away, with GeoIP off and no person profile, so
 * PostHog keeps neither a location from our server's address nor a person
 * (docs/contracts/05-desktop-telemetry.md). Never throws: posthog-node logs
 * and drops a failed send.
 */
export function createPersonlessCapture({ apiKey, host, fetch }: CaptureConfig): CapturePersonless {
	if (!apiKey) return async () => {};

	const client = new PostHog(apiKey, {
		host: host || undefined,
		disableGeoip: true,
		flushAt: 1,
		flushInterval: 0,
		requestTimeout: 5000,
		fetchRetryCount: 1,
		fetch,
	});

	return async ({ event, properties }) => {
		await client.captureImmediate({
			// A fresh id per event: there is no one to count twice and nothing to join on.
			distinctId: randomUUID(),
			event,
			properties: { ...properties, $process_person_profile: false },
			disableGeoip: true,
		});
	};
}

let captureFromEnv: CapturePersonless | undefined;

/**
 * The routes' capture. Does nothing until DESKTOP_TELEMETRY_POSTHOG_KEY is set.
 * The key's project must live on the instance NEXT_PUBLIC_POSTHOG_HOST names
 * (fixed at build time), or PostHog drops every event without an error.
 */
export function capturePersonlessEvent(event: PersonlessEvent): Promise<void> {
	captureFromEnv ??= createPersonlessCapture({
		apiKey: process.env.DESKTOP_TELEMETRY_POSTHOG_KEY,
		host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
	});
	return captureFromEnv(event);
}
